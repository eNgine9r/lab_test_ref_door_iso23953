import atexit
import json
import logging
import os
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import config
from cycle_counter import CycleCounter
from door_logic import DoorLogic
from logger import get_test_logger
from modbus_client import ModbusClientFactory
from relay_controller import RelayController
from test_logic import ISO23953DoorTest

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = APP_DIR / "config.json"

app = Flask(__name__)

logging.basicConfig(
    filename=config.LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M",
)


def load_runtime_config() -> dict:
    if DEFAULT_CONFIG_PATH.exists():
        with DEFAULT_CONFIG_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    return {}


runtime_config = load_runtime_config()
default_modbus = runtime_config.get("modbus", {})
if default_modbus.get("port"):
    os.environ.setdefault("MODBUS_PORT", str(default_modbus["port"]))
if default_modbus.get("baudrate"):
    os.environ.setdefault("MODBUS_BAUDRATE", str(default_modbus["baudrate"]))
if default_modbus.get("slave_id"):
    os.environ.setdefault("MODBUS_SLAVE_ID", str(default_modbus["slave_id"]))
if default_modbus.get("backend"):
    os.environ.setdefault("MODBUS_BACKEND", str(default_modbus["backend"]))


def log_event(event: str, status: str = "OK"):
    logging.info("%s | %s", event, status)
    with state_lock:
        state["last_event"] = event
        state["error_message"] = "" if status == "OK" else event


simulation_mode = runtime_config.get("simulation", config.SIMULATION_MODE)
controller = ModbusClientFactory.create(simulation_mode=bool(simulation_mode))
relay_logger = get_test_logger("web")
relay = RelayController(controller, relay_logger)
connected = relay.connect()
counter = CycleCounter(config.CYCLES_FILE, doors=config.MAX_DOORS)
logic = DoorLogic(controller, log_event, showcase_type=config.SHOWCASE_TYPE)

state_lock = threading.Lock()
test_lock = threading.Lock()
current_test = None
current_thread = None
state = {
    "running": False,
    "status": "READY" if connected or simulation_mode else "ERROR",
    "last_event": "system start",
    "error_message": "" if connected or simulation_mode else "modbus connect failed",
    "open_time": runtime_config.get("open_time", config.DEFAULT_OPEN_TIME),
    "delay_between_doors": runtime_config.get("delay_between_doors", config.DEFAULT_DELAY),
    "showcase_type": runtime_config.get("mode", "MT"),
    "door_count": max(1, min(int(runtime_config.get("doors", config.DOOR_COUNT)), 5)),
    "started_at": None,
    "test_mode": runtime_config.get("mode", "MT"),
    "light_relay_on": False,
    "light_channel": RelayController.LIGHT_CHANNEL,
    "light_off_after_seconds": 12 * 3600,
    "modbus_connected": connected if not simulation_mode else True,
    "modbus_port": getattr(controller, "active_port", lambda: "simulator")(),
    "modbus_backend": getattr(controller, "active_backend", lambda: "simulator")(),
    "test_duration_hours": int(runtime_config.get("test_duration_hours", 12)),
    "debug": bool(runtime_config.get("debug", False)),
}


def _set_door_state(channel: int, status_value: str):
    if 1 <= channel <= config.MAX_DOORS:
        logic._door_state[f"door{channel}"] = status_value


class ObservableRelayController(RelayController):
    def record_cycle(self, door: int):
        counter.add_cycle(door - 1)

    def open_relay(self, channel: int):
        super().open_relay(channel)
        with state_lock:
            if channel == self.LIGHT_CHANNEL:
                state["light_relay_on"] = True
            else:
                _set_door_state(channel, "open")
        if channel != self.LIGHT_CHANNEL:
            counter.add_transition_event(channel - 1, "open", datetime.now().isoformat(timespec="seconds"))

    def close_relay(self, channel: int):
        super().close_relay(channel)
        with state_lock:
            if channel == self.LIGHT_CHANNEL:
                state["light_relay_on"] = False
            else:
                _set_door_state(channel, "closed")
        if channel != self.LIGHT_CHANNEL:
            counter.add_transition_event(channel - 1, "close", datetime.now().isoformat(timespec="seconds"))


web_relay = ObservableRelayController(controller, relay_logger)


def build_test_config(payload: dict) -> dict:
    mode = str(payload.get("mode", state["test_mode"]))
    mode = mode.upper() if mode else "MT"
    doors = max(1, min(int(payload.get("door_count", state["door_count"])), 5))
    duration = max(1, int(payload.get("test_duration_hours", state["test_duration_hours"])))
    debug = bool(payload.get("debug", state["debug"]))
    config_data = dict(runtime_config)
    config_data.update(
        {
            "mode": mode,
            "doors": doors,
            "test_duration_hours": duration,
            "debug": debug,
        }
    )
    return config_data



def run_iso_test(test_config: dict):
    global current_test, current_thread
    test = ISO23953DoorTest(test_config, web_relay, relay_logger, register_signals=False)
    with test_lock:
        current_test = test
        current_thread = threading.current_thread()

    try:
        relay_logger.info("web ui started test mode=%s doors=%s duration=%s debug=%s", test_config["mode"], test_config["doors"], test_config["test_duration_hours"], test_config.get("debug", False))
        test.run()
        if test.stopped_early:
            with state_lock:
                state["status"] = "STOPPED"
                state["running"] = False
                state["last_event"] = "test stopped"
        else:
            with state_lock:
                state["status"] = "READY"
                state["running"] = False
                state["last_event"] = "test completed"
    except Exception as exc:  # noqa: BLE001
        with state_lock:
            state["status"] = "ERROR"
            state["running"] = False
            state["error_message"] = str(exc)
        log_event(f"web test error: {exc}", "ERROR")
    finally:
        with state_lock:
            state["modbus_connected"] = True if simulation_mode else controller.ping()
            state["modbus_port"] = getattr(controller, "active_port", lambda: "simulator")()
            state["modbus_backend"] = getattr(controller, "active_backend", lambda: "simulator")()
        with test_lock:
            current_test = None
            current_thread = None


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
        state["error_message"] = ""
        state["started_at"] = datetime.now().isoformat()

    test_config = build_test_config(payload)
    with state_lock:
        state["door_count"] = test_config["doors"]
        state["test_mode"] = test_config["mode"]
        state["showcase_type"] = test_config["mode"]
        state["test_duration_hours"] = test_config["test_duration_hours"]
        state["debug"] = test_config["debug"]

    thread = threading.Thread(target=run_iso_test, args=(test_config,), daemon=True)
    thread.start()
    log_event(f"test start ({test_config['mode']})", "OK")
    return jsonify({"message": "started", "config": test_config})


@app.route("/stop", methods=["POST"])
def stop_test():
    with test_lock:
        test = current_test
    if test is not None:
        test.stop("stopped from web ui")
    with state_lock:
        state["running"] = False
        state["status"] = "STOPPED"
        state["last_event"] = "test stop requested"
    return jsonify({"message": "stop requested"})


@app.route("/reset", methods=["POST"])
def reset_cycles():
    counter.reset()
    log_event("cycles reset", "OK")
    return jsonify({"message": "reset"})


@app.route("/open/<int:door>", methods=["POST"])
def manual_open(door: int):
    with state_lock:
        allowed_doors = state["door_count"]
    if not 1 <= door <= allowed_doors:
        return jsonify({"error": "invalid door"}), 400
    try:
        logic.open_door(door - 1, on_transition=counter.add_transition_event)
        time.sleep(float(state["open_time"]))
        logic.close_door(door - 1, on_transition=counter.add_transition_event)
        counter.add_cycle(door - 1)
        return jsonify({"message": f"door {door} cycled"})
    except Exception as exc:  # noqa: BLE001
        log_event(f"manual open error: {exc}", "ERROR")
        return jsonify({"error": str(exc)}), 500


@app.route("/light", methods=["POST"])
def toggle_light():
    payload = request.get_json(silent=True) or {}
    value = bool(payload.get("on", False))
    try:
        web_relay.set_light(value)
        return jsonify({"light_relay_on": state["light_relay_on"]})
    except Exception as exc:  # noqa: BLE001
        log_event(f"light relay error: {exc}", "ERROR")
        return jsonify({"error": str(exc)}), 500


@app.route("/cycles")
def get_cycles():
    return jsonify({"cycles": counter.get_cycles(), "events": counter.get_events(limit=300)})


@app.route("/status")
def get_status():
    with state_lock:
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
                "test_duration_hours": state["test_duration_hours"],
                "debug": state["debug"],
            }
        )


@atexit.register
def _shutdown():
    with test_lock:
        test = current_test
    if test is not None:
        test.stop("application shutdown")
    with state_lock:
        state["running"] = False
    try:
        web_relay.close_all_relays()
    except Exception:
        pass
    controller.close()


if __name__ == "__main__":
    if connected or simulation_mode:
        log_event("web interface ready", "OK")
    else:
        log_event("modbus connect failed", "ERROR")

    if os.getenv("AUTO_OPEN_BROWSER", "0") in {"1", "true", "True"}:
        timer = threading.Timer(1.5, lambda: webbrowser.open(f"http://{config.HOST}:{config.PORT}/"))
        timer.daemon = True
        timer.start()

    app.run(host=config.HOST, port=config.PORT)
