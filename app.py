import atexit
import logging
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, render_template, request

import config
from cycle_counter import CycleCounter
from door_logic import DoorLogic
from hardware_simulator import HardwareSimulator
from watchdog import SystemWatchdog

app = Flask(__name__)

logging.basicConfig(
    filename=config.LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M",
)


def log_event(event: str, status: str = "OK"):
    logging.info("%s | %s", event, status)
    state["last_event"] = event
    state["error_message"] = "" if status == "OK" else event


if config.SIMULATION_MODE:
    controller = HardwareSimulator()
else:
    from modbus_controller import ModbusController

    controller = ModbusController()
connected = controller.connect()
counter = CycleCounter(config.CYCLES_FILE, doors=min(config.DOOR_COUNT, config.MAX_DOORS))
logic = DoorLogic(controller, log_event, showcase_type=config.SHOWCASE_TYPE)

state_lock = threading.Lock()
state = {
    "running": False,
    "status": "READY",
    "last_event": "system start",
    "error_message": "",
    "open_time": config.DEFAULT_OPEN_TIME,
    "delay_between_doors": config.DEFAULT_DELAY,
    "showcase_type": config.SHOWCASE_TYPE,
    "door_count": min(config.DOOR_COUNT, config.MAX_DOORS),
    "started_at": None,
    "test_mode": "day",
    "light_relay_on": True,
    "light_off_after_seconds": 12 * 3600,
    "light_channel": config.LIGHT_RELAY_CHANNEL,
    "modbus_connected": connected if not config.SIMULATION_MODE else True,
    "modbus_port": getattr(controller, "active_port", lambda: "simulator")(),
    "modbus_backend": getattr(controller, "active_backend", lambda: "simulator")(),
}




def set_light(state_on: bool):
    if not state.get("modbus_connected", True) and not config.SIMULATION_MODE:
        raise RuntimeError("modbus not connected")
    controller.write_coil(state["light_channel"], state_on)
    state["light_relay_on"] = state_on
    log_event("light relay ON" if state_on else "light relay OFF", "OK")


def check_and_apply_light_schedule():
    if not state["running"] or state["test_mode"] != "day" or not state["started_at"]:
        return
    started = datetime.fromisoformat(state["started_at"])
    elapsed = (datetime.now() - started).total_seconds()
    if elapsed >= state["light_off_after_seconds"] and state["light_relay_on"]:
        set_light(False)


def enter_fail_safe(reason: str):
    with state_lock:
        state["running"] = False
        state["status"] = "ERROR"
        state["error_message"] = reason
        if not config.SIMULATION_MODE:
            state["modbus_connected"] = False
    try:
        logic.safe_shutdown(config.MAX_DOORS)
        set_light(False)
    except Exception as exc:  # noqa: BLE001
        log_event(f"safe shutdown failed: {exc}", "ERROR")
    log_event(reason, "ERROR")


def watchdog_timeout_handler():
    enter_fail_safe("watchdog timeout")


watchdog = SystemWatchdog(config.WATCHDOG_TIMEOUT, watchdog_timeout_handler)
watchdog.start()


def _run_test_loop():
    while True:
        with state_lock:
            if not state["running"]:
                break
            open_time = state["open_time"]
            delay = state["delay_between_doors"]
            door_count = state["door_count"]

        check_and_apply_light_schedule()

        try:
            controller.ping()
        except Exception:  # noqa: BLE001
            enter_fail_safe("MODBUS CONNECTION LOST")
            break

        for door in range(door_count):
            with state_lock:
                if not state["running"]:
                    break
            try:
                logic.test_cycle(
                    door,
                    open_time,
                    delay,
                    tick=watchdog.tick,
                    cycle_warning=lambda msg: log_event(msg, "WARN"),
                    on_transition=counter.add_transition_event,
                )
                counter.add_cycle(door)
                watchdog.tick()
                check_and_apply_light_schedule()
            except Exception as exc:  # noqa: BLE001
                enter_fail_safe(f"modbus error: {exc}")
                return


def reconnect_worker():
    while True:
        time.sleep(config.RECONNECT_INTERVAL)
        with state_lock:
            need_reconnect = state["status"] == "ERROR"
        if not need_reconnect:
            continue
        try:
            if controller.connect() and controller.ping():
                with state_lock:
                    state["status"] = "READY"
                    state["error_message"] = ""
                    state["modbus_connected"] = True
                    state["modbus_port"] = getattr(controller, "active_port", lambda: "simulator")()
                    state["modbus_backend"] = getattr(controller, "active_backend", lambda: "simulator")()
                log_event("connection recovered", "OK")
            else:
                with state_lock:
                    state["modbus_connected"] = False
        except Exception:  # noqa: BLE001
            pass


threading.Thread(target=reconnect_worker, daemon=True).start()


@app.route("/")
def root():
    return render_template("dashboard.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/start", methods=["POST"])
def start_test():
    payload = request.get_json(silent=True) or {}
    with state_lock:
        if state["running"]:
            return jsonify({"message": "Test already running"}), 200
        state["running"] = True
        state["status"] = "RUNNING"
        state["open_time"] = float(payload.get("open_time", state["open_time"]))
        state["delay_between_doors"] = float(payload.get("delay_between_doors", state["delay_between_doors"]))
        state["showcase_type"] = payload.get("showcase_type", state["showcase_type"])
        requested_doors = int(payload.get("door_count", state["door_count"]))
        state["door_count"] = max(1, min(requested_doors, config.MAX_DOORS))
        state["test_mode"] = payload.get("test_mode", "day")
        state["started_at"] = datetime.now().isoformat()
        logic.showcase_type = state["showcase_type"]
        set_light(True)

    threading.Thread(target=_run_test_loop, daemon=True).start()
    log_event("test start", "OK")
    return jsonify({"message": "started"})


@app.route("/stop", methods=["POST"])
def stop_test():
    with state_lock:
        state["running"] = False
        state["status"] = "STOPPED"
    logic.safe_shutdown(config.MAX_DOORS)
    set_light(False)
    log_event("test stop", "OK")
    return jsonify({"message": "stopped"})


@app.route("/reset", methods=["POST"])
def reset_cycles():
    counter.reset()
    log_event("cycles reset", "OK")
    return jsonify({"message": "reset"})


@app.route("/open/<int:door>", methods=["POST"])
def manual_open(door: int):
    if not 1 <= door <= state["door_count"]:
        return jsonify({"error": "invalid door"}), 400
    try:
        logic.open_door(door - 1, on_transition=counter.add_transition_event)
        time.sleep(state["open_time"])
        logic.close_door(door - 1, on_transition=counter.add_transition_event)
        counter.add_cycle(door - 1)
        watchdog.tick()
        return jsonify({"message": f"door {door} cycled"})
    except Exception as exc:  # noqa: BLE001
        enter_fail_safe(f"manual open error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/light", methods=["POST"])
def toggle_light():
    payload = request.get_json(silent=True) or {}
    value = bool(payload.get("on", False))
    try:
        set_light(value)
        return jsonify({"light_relay_on": state["light_relay_on"]})
    except Exception as exc:  # noqa: BLE001
        enter_fail_safe(f"light relay error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/cycles")
def get_cycles():
    return jsonify({"cycles": counter.get_cycles(), "events": counter.get_events(limit=300)})


@app.route("/status")
def get_status():
    return jsonify(
        {
            "system_status": state["status"],
            "test_running": state["running"],
            "last_event": state["last_event"],
            "error_message": state["error_message"],
            "doors": logic.get_states(),
            "light_relay_on": state["light_relay_on"],
            "test_mode": state["test_mode"],
            "door_count": state["door_count"],
            "modbus_connected": state["modbus_connected"],
            "modbus_port": state["modbus_port"],
            "modbus_backend": state["modbus_backend"],
        }
    )


@atexit.register
def _shutdown():
    with state_lock:
        state["running"] = False
    watchdog.stop()
    logic.safe_shutdown(config.MAX_DOORS)
    try:
        set_light(False)
    except Exception:
        pass
    controller.close()


if __name__ == "__main__":
    if not config.SIMULATION_MODE and not connected:
        state["status"] = "ERROR"
        state["error_message"] = "modbus connect failed"
        log_event("modbus connect failed", "ERROR")
    else:
        log_event("system start", "OK")
    app.run(host=config.HOST, port=config.PORT)
