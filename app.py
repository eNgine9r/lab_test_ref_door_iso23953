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
controller.connect()
counter = CycleCounter(config.CYCLES_FILE, doors=config.DOOR_COUNT)
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
    "door_count": config.DOOR_COUNT,
    "started_at": None,
    "history": [],
}


def enter_fail_safe(reason: str):
    with state_lock:
        state["running"] = False
        state["status"] = "ERROR"
        state["error_message"] = reason
    try:
        logic.safe_shutdown(config.DOOR_COUNT)
    except Exception as exc:  # noqa: BLE001
        log_event(f"safe shutdown failed: {exc}", "ERROR")
    log_event(reason, "ERROR")


def watchdog_timeout_handler():
    enter_fail_safe("watchdog timeout")


watchdog = SystemWatchdog(config.WATCHDOG_TIMEOUT, watchdog_timeout_handler)
watchdog.start()


def append_history():
    point = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        **counter.get_cycles(),
    }
    state["history"].append(point)
    state["history"] = state["history"][-120:]


def _run_test_loop():
    while True:
        with state_lock:
            if not state["running"]:
                break
            open_time = state["open_time"]
            delay = state["delay_between_doors"]
            door_count = state["door_count"]

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
                )
                counter.add_cycle(door)
                append_history()
                watchdog.tick()
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
                log_event("connection recovered", "OK")
        except Exception:  # noqa: BLE001
            pass


threading.Thread(target=reconnect_worker, daemon=True).start()


def simulation_data_generator():
    while True:
        time.sleep(5)
        if not config.SIMULATION_MODE:
            continue
        with state_lock:
            if state["running"]:
                continue
        counter.add_cycle(0)
        if config.DOOR_COUNT > 1 and int(time.time()) % 6 == 0:
            counter.add_cycle(1)
        append_history()


threading.Thread(target=simulation_data_generator, daemon=True).start()


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
        state["door_count"] = int(payload.get("door_count", state["door_count"]))
        state["started_at"] = datetime.now().isoformat()
        logic.showcase_type = state["showcase_type"]

    threading.Thread(target=_run_test_loop, daemon=True).start()
    log_event("test start", "OK")
    return jsonify({"message": "started"})


@app.route("/stop", methods=["POST"])
def stop_test():
    with state_lock:
        state["running"] = False
        state["status"] = "STOPPED"
    logic.safe_shutdown(config.DOOR_COUNT)
    log_event("test stop", "OK")
    return jsonify({"message": "stopped"})


@app.route("/reset", methods=["POST"])
def reset_cycles():
    counter.reset()
    append_history()
    log_event("cycles reset", "OK")
    return jsonify({"message": "reset"})


@app.route("/open/<int:door>", methods=["POST"])
def manual_open(door: int):
    if not 1 <= door <= config.DOOR_COUNT:
        return jsonify({"error": "invalid door"}), 400
    try:
        logic.open_door(door - 1)
        time.sleep(state["open_time"])
        logic.close_door(door - 1)
        counter.add_cycle(door - 1)
        append_history()
        watchdog.tick()
        return jsonify({"message": f"door {door} cycled"})
    except Exception as exc:  # noqa: BLE001
        enter_fail_safe(f"manual open error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/cycles")
def get_cycles():
    return jsonify({"cycles": counter.get_cycles(), "history": state["history"]})


@app.route("/status")
def get_status():
    return jsonify(
        {
            "system_status": state["status"],
            "test_running": state["running"],
            "last_event": state["last_event"],
            "error_message": state["error_message"],
            "doors": logic.get_states(),
        }
    )


@atexit.register
def _shutdown():
    with state_lock:
        state["running"] = False
    watchdog.stop()
    logic.safe_shutdown(config.DOOR_COUNT)
    controller.close()


if __name__ == "__main__":
    append_history()
    log_event("system start", "OK")
    app.run(host=config.HOST, port=config.PORT)
