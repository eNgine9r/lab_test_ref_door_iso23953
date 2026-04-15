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
from logger import get_rotating_handler, get_test_logger
from modbus_client import ModbusClientFactory
from relay_controller import RelayController
from test_logic import ISO23953DoorTest

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = APP_DIR / "config.json"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M"
STARTUP_LIGHT_RETRIES = 8
STARTUP_LIGHT_RETRY_DELAY_SEC = 2

app = Flask(__name__)

app_logger = logging.getLogger()
app_logger.setLevel(logging.INFO)
if not app_logger.handlers:
    app_handler = get_rotating_handler(str(config.LOG_FILE), datefmt="%d/%m/%y %H:%M:%S")
    app_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", "%d/%m/%y %H:%M:%S"))
    app_logger.addHandler(app_handler)


def load_runtime_config() -> dict:
    if DEFAULT_CONFIG_PATH.exists():
        with DEFAULT_CONFIG_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def current_form_state() -> dict:
    with state_lock:
        return {
            "mode": state["selected_mode"],
            "door_count": state["selected_door_count"],
            "test_duration_hours": state["selected_test_duration_hours"],
            "debug": state["selected_debug"],
            "schedule_enabled": state["schedule_enabled"],
            "scheduled_start": state["scheduled_start"],
            "door_open_time_sec": state["selected_door_open_time_sec"],
            "door_close_time_sec": state["selected_door_close_time_sec"],
            "post_test_light_enabled": state["selected_post_test_light_enabled"],
            "post_test_light_delay_hours": state["selected_post_test_light_delay_hours"],
            "post_test_light_delay_minutes": state["selected_post_test_light_delay_minutes"],
        }


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
scheduler_thread = None
scheduler_cancel = threading.Event()
post_test_timer_thread = None
post_test_timer_cancel = threading.Event()
default_mode = str(runtime_config.get("mode", "MT")).upper()
default_doors = max(1, min(int(runtime_config.get("doors", config.DOOR_COUNT)), 5))
default_duration = int(runtime_config.get("test_duration_hours", 12))
default_debug = bool(runtime_config.get("debug", False))
default_scheduled_start = runtime_config.get("scheduled_start", "")
default_schedule_enabled = bool(default_scheduled_start)
default_door_open_time_sec = float(runtime_config.get("door_open_time_sec", os.getenv("DOOR_OPEN_TIME_SEC", "0.5")))
default_door_close_time_sec = float(runtime_config.get("door_close_time_sec", os.getenv("DOOR_CLOSE_TIME_SEC", "0.5")))
state = {
    "running": False,
    "status": "READY" if connected or simulation_mode else "ERROR",
    "last_event": "system start",
    "error_message": "" if connected or simulation_mode else "modbus connect failed",
    "open_time": runtime_config.get("open_time", config.DEFAULT_OPEN_TIME),
    "delay_between_doors": runtime_config.get("delay_between_doors", config.DEFAULT_DELAY),
    "showcase_type": default_mode,
    "door_count": default_doors,
    "started_at": None,
    "test_mode": default_mode,
    "light_relay_on": False,
    "light_channel": RelayController.LIGHT_CHANNEL,
    "light_off_after_seconds": 12 * 3600,
    "modbus_connected": connected if not simulation_mode else True,
    "modbus_port": getattr(controller, "active_port", lambda: "simulator")(),
    "modbus_backend": getattr(controller, "active_backend", lambda: "simulator")(),
    "test_duration_hours": default_duration,
    "debug": default_debug,
    "selected_mode": default_mode,
    "selected_door_count": default_doors,
    "selected_test_duration_hours": default_duration,
    "selected_debug": default_debug,
    "schedule_enabled": default_schedule_enabled,
    "scheduled_start": default_scheduled_start,
    "schedule_status": "IDLE",
    "selected_door_open_time_sec": default_door_open_time_sec,
    "selected_door_close_time_sec": default_door_close_time_sec,
    "door_open_time_sec": default_door_open_time_sec,
    "door_close_time_sec": default_door_close_time_sec,
    "selected_post_test_light_enabled": bool(runtime_config.get("post_test_light_enabled", False)),
    "selected_post_test_light_delay_hours": int(runtime_config.get("post_test_light_delay_hours", 0)),
    "selected_post_test_light_delay_minutes": int(runtime_config.get("post_test_light_delay_minutes", 0)),
    "post_test_light_enabled": bool(runtime_config.get("post_test_light_enabled", False)),
    "post_test_light_delay_hours": int(runtime_config.get("post_test_light_delay_hours", 0)),
    "post_test_light_delay_minutes": int(runtime_config.get("post_test_light_delay_minutes", 0)),
    "post_test_light_status": "IDLE",
    "post_test_light_remaining_seconds": None,
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
            counter.add_transition_event(channel - 1, "open", datetime.now().strftime("%d/%m/%y %H:%M:%S"))

    def close_relay(self, channel: int):
        super().close_relay(channel)
        with state_lock:
            if channel == self.LIGHT_CHANNEL:
                state["light_relay_on"] = False
            else:
                _set_door_state(channel, "closed")
        if channel != self.LIGHT_CHANNEL:
            counter.add_transition_event(channel - 1, "close", datetime.now().strftime("%d/%m/%y %H:%M:%S"))


web_relay = ObservableRelayController(controller, relay_logger)


def ensure_startup_light_on() -> bool:
    if simulation_mode:
        web_relay.set_light(True)
        return True

    for attempt in range(1, STARTUP_LIGHT_RETRIES + 1):
        try:
            if not controller.ping():
                controller.connect()
            web_relay.set_light(True)
            with state_lock:
                state["modbus_connected"] = True
            log_event(f"relay 6 auto ON at startup (attempt {attempt})", "OK")
            return True
        except Exception as exc:  # noqa: BLE001
            relay_logger.warning("startup light relay attempt %s failed: %s", attempt, exc)
            time.sleep(STARTUP_LIGHT_RETRY_DELAY_SEC)

    with state_lock:
        state["modbus_connected"] = False
        state["status"] = "ERROR"
        state["error_message"] = "failed to enable relay 6 on startup"
    log_event("failed to enable relay 6 on startup", "ERROR")
    return False


def parse_schedule_datetime(raw_value: str) -> str:
    if not raw_value:
        return ""
    scheduled = datetime.strptime(raw_value, DATETIME_FORMAT)
    if scheduled <= datetime.now():
        raise ValueError("Scheduled start must be in the future")
    return scheduled.strftime(DATETIME_FORMAT)


def build_test_config(payload: dict) -> dict:
    mode = str(payload.get("mode", current_form_state()["mode"]))
    mode = mode.upper() if mode else "MT"
    doors = max(1, min(int(payload.get("door_count", current_form_state()["door_count"])), 5))
    duration = max(1, int(payload.get("test_duration_hours", current_form_state()["test_duration_hours"])))
    debug = bool(payload.get("debug", current_form_state()["debug"]))
    schedule_enabled = bool(payload.get("schedule_enabled", False))
    scheduled_start = parse_schedule_datetime(payload.get("scheduled_start", "")) if schedule_enabled else ""
    door_open_time_sec = max(0.0, float(payload.get("door_open_time_sec", current_form_state()["door_open_time_sec"])))
    door_close_time_sec = max(0.0, float(payload.get("door_close_time_sec", current_form_state()["door_close_time_sec"])))
    post_test_light_enabled = bool(payload.get("post_test_light_enabled", current_form_state()["post_test_light_enabled"]))
    post_test_light_delay_hours = max(0, int(payload.get("post_test_light_delay_hours", current_form_state()["post_test_light_delay_hours"])))
    post_test_light_delay_minutes = max(0, min(59, int(payload.get("post_test_light_delay_minutes", current_form_state()["post_test_light_delay_minutes"]))))

    config_data = dict(runtime_config)
    config_data.update(
        {
            "mode": mode,
            "doors": doors,
            "test_duration_hours": duration,
            "debug": debug,
            "schedule": {
                "enabled": schedule_enabled,
                "start_time": scheduled_start,
            },
            "scheduled_start": scheduled_start,
            "door_open_time_sec": door_open_time_sec,
            "door_close_time_sec": door_close_time_sec,
            "post_test_light_enabled": post_test_light_enabled,
            "post_test_light_delay_hours": post_test_light_delay_hours,
            "post_test_light_delay_minutes": post_test_light_delay_minutes,
        }
    )
    return config_data


def apply_selected_state(test_config: dict):
    with state_lock:
        state["selected_mode"] = test_config["mode"]
        state["selected_door_count"] = test_config["doors"]
        state["selected_test_duration_hours"] = test_config["test_duration_hours"]
        state["selected_debug"] = test_config["debug"]
        state["schedule_enabled"] = bool(test_config.get("schedule", {}).get("enabled", False))
        state["scheduled_start"] = test_config.get("scheduled_start", "")
        state["selected_door_open_time_sec"] = float(test_config.get("door_open_time_sec", state["selected_door_open_time_sec"]))
        state["selected_door_close_time_sec"] = float(test_config.get("door_close_time_sec", state["selected_door_close_time_sec"]))
        state["selected_post_test_light_enabled"] = bool(test_config.get("post_test_light_enabled", state["selected_post_test_light_enabled"]))
        state["selected_post_test_light_delay_hours"] = int(test_config.get("post_test_light_delay_hours", state["selected_post_test_light_delay_hours"]))
        state["selected_post_test_light_delay_minutes"] = int(test_config.get("post_test_light_delay_minutes", state["selected_post_test_light_delay_minutes"]))


def mark_test_active(test_config: dict):
    with state_lock:
        state["running"] = True
        state["status"] = "RUNNING"
        state["error_message"] = ""
        state["started_at"] = datetime.now().strftime("%d/%m/%y %H:%M:%S")
        state["door_count"] = test_config["doors"]
        state["test_mode"] = test_config["mode"]
        state["showcase_type"] = test_config["mode"]
        state["test_duration_hours"] = test_config["test_duration_hours"]
        state["debug"] = test_config["debug"]
        state["schedule_status"] = "IDLE"
        state["scheduled_start"] = test_config.get("scheduled_start", "")
        state["door_open_time_sec"] = float(test_config.get("door_open_time_sec", state["door_open_time_sec"]))
        state["door_close_time_sec"] = float(test_config.get("door_close_time_sec", state["door_close_time_sec"]))
        state["post_test_light_enabled"] = bool(test_config.get("post_test_light_enabled", state["post_test_light_enabled"]))
        state["post_test_light_delay_hours"] = int(test_config.get("post_test_light_delay_hours", state["post_test_light_delay_hours"]))
        state["post_test_light_delay_minutes"] = int(test_config.get("post_test_light_delay_minutes", state["post_test_light_delay_minutes"]))
        state["post_test_light_status"] = "IDLE"
        state["post_test_light_remaining_seconds"] = None



def cancel_post_test_timer():
    post_test_timer_cancel.set()
    with state_lock:
        state["post_test_light_status"] = "IDLE"
        state["post_test_light_remaining_seconds"] = None


def schedule_post_test_light(test_config: dict):
    global post_test_timer_thread
    enabled = bool(test_config.get("post_test_light_enabled", False))
    delay_seconds = int(test_config.get("post_test_light_delay_hours", 0)) * 3600 + int(test_config.get("post_test_light_delay_minutes", 0)) * 60

    if not enabled:
        relay_logger.info("post-test light activation disabled")
        return

    relay_logger.info(
        "post-test light activation enabled, delay=%sh %sm",
        int(test_config.get("post_test_light_delay_hours", 0)),
        int(test_config.get("post_test_light_delay_minutes", 0)),
    )

    post_test_timer_cancel.clear()

    def worker():
        with state_lock:
            state["post_test_light_status"] = "WAITING"
            state["post_test_light_remaining_seconds"] = delay_seconds

        started = time.monotonic()
        while not post_test_timer_cancel.is_set():
            elapsed = int(time.monotonic() - started)
            remaining = max(0, delay_seconds - elapsed)
            with state_lock:
                state["post_test_light_remaining_seconds"] = remaining
            if remaining <= 0:
                break
            time.sleep(1)

        if post_test_timer_cancel.is_set():
            relay_logger.info("post-test light timer canceled")
            with state_lock:
                state["post_test_light_status"] = "CANCELED"
                state["post_test_light_remaining_seconds"] = None
            return

        try:
            web_relay.set_light(True)
            with state_lock:
                state["showcase_type"] = "day"
                state["post_test_light_status"] = "COMPLETED"
                state["post_test_light_remaining_seconds"] = 0
            relay_logger.info("post-test light activation completed")
            log_event("post-test timer complete: light ON, day mode set", "OK")
        except Exception as exc:  # noqa: BLE001
            with state_lock:
                state["post_test_light_status"] = "ERROR"
                state["post_test_light_remaining_seconds"] = None
            relay_logger.error("post-test light activation failed: %s", exc)
            log_event(f"post-test light activation error: {exc}", "ERROR")

    post_test_timer_thread = threading.Thread(target=worker, daemon=True)
    post_test_timer_thread.start()


def run_iso_test(test_config: dict):
    global current_test
    cancel_post_test_timer()
    test = ISO23953DoorTest(test_config, web_relay, relay_logger, register_signals=False)
    with test_lock:
        current_test = test

    try:
        relay_logger.info(
            "web ui started test mode=%s doors=%s duration=%s debug=%s",
            test_config["mode"],
            test_config["doors"],
            test_config["test_duration_hours"],
            test_config.get("debug", False),
        )
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
            schedule_post_test_light(test_config)
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
            if state["schedule_status"] != "WAITING":
                state["scheduled_start"] = ""
                state["schedule_enabled"] = False
                state["schedule_status"] = "IDLE"
        with test_lock:
            current_test = None


def launch_test(test_config: dict):
    apply_selected_state(test_config)
    mark_test_active(test_config)
    thread = threading.Thread(target=run_iso_test, args=(test_config,), daemon=True)
    thread.start()
    log_event(f"test start ({test_config['mode']})", "OK")
    return thread


def schedule_test_run(test_config: dict):
    global scheduler_thread
    scheduled_raw = test_config.get("scheduled_start", "")
    scheduled_at = datetime.strptime(scheduled_raw, DATETIME_FORMAT)

    def worker():
        with state_lock:
            state["schedule_status"] = "WAITING"
            state["status"] = "SCHEDULED"
            state["running"] = False
            state["scheduled_start"] = scheduled_raw
        log_event(f"test scheduled for {scheduled_raw}", "OK")

        while not scheduler_cancel.is_set():
            seconds_left = (scheduled_at - datetime.now()).total_seconds()
            if seconds_left <= 0:
                break
            time.sleep(min(1, max(0.1, seconds_left)))

        if scheduler_cancel.is_set():
            with state_lock:
                state["status"] = "STOPPED"
                state["schedule_status"] = "IDLE"
                state["scheduled_start"] = ""
                state["schedule_enabled"] = False
                state["last_event"] = "scheduled test cancelled"
            return

        launch_test({**test_config, "schedule": {"enabled": False, "start_time": ""}, "scheduled_start": ""})

    cancel_post_test_timer()
    scheduler_cancel.clear()
    scheduler_thread = threading.Thread(target=worker, daemon=True)
    scheduler_thread.start()


@app.route("/")
def root():
    return render_template("dashboard.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/start", methods=["POST"])
def start_test():
    global scheduler_thread
    payload = request.get_json(silent=True) or {}
    with state_lock:
        if state["running"] or state["schedule_status"] == "WAITING":
            return jsonify({"message": "Test already running or scheduled"}), 200

    test_config = build_test_config(payload)
    apply_selected_state(test_config)

    if test_config.get("schedule", {}).get("enabled"):
        schedule_test_run(test_config)
        return jsonify({"message": "scheduled", "config": test_config})

    cancel_post_test_timer()
    scheduler_cancel.clear()
    scheduler_thread = None
    launch_test(test_config)
    return jsonify({"message": "started", "config": test_config})


@app.route("/stop", methods=["POST"])
def stop_test():
    scheduler_cancel.set()
    cancel_post_test_timer()
    with test_lock:
        test = current_test
    if test is not None:
        test.stop("stopped from web ui")
    with state_lock:
        state["running"] = False
        state["status"] = "STOPPED"
        state["schedule_status"] = "IDLE"
        state["scheduled_start"] = ""
        state["schedule_enabled"] = False
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
        allowed_doors = state["selected_door_count"]
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
        seconds_until_start = None
        if state["scheduled_start"]:
            try:
                target = datetime.strptime(state["scheduled_start"], DATETIME_FORMAT)
                seconds_until_start = max(0, int((target - datetime.now()).total_seconds()))
            except ValueError:
                seconds_until_start = None
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
                "selected_mode": state["selected_mode"],
                "selected_door_count": state["selected_door_count"],
                "selected_test_duration_hours": state["selected_test_duration_hours"],
                "selected_debug": state["selected_debug"],
                "schedule_enabled": state["schedule_enabled"],
                "scheduled_start": state["scheduled_start"],
                "schedule_status": state["schedule_status"],
                "seconds_until_start": seconds_until_start,
                "selected_door_open_time_sec": state["selected_door_open_time_sec"],
                "selected_door_close_time_sec": state["selected_door_close_time_sec"],
                "door_open_time_sec": state["door_open_time_sec"],
                "door_close_time_sec": state["door_close_time_sec"],
                "selected_post_test_light_enabled": state["selected_post_test_light_enabled"],
                "selected_post_test_light_delay_hours": state["selected_post_test_light_delay_hours"],
                "selected_post_test_light_delay_minutes": state["selected_post_test_light_delay_minutes"],
                "post_test_light_enabled": state["post_test_light_enabled"],
                "post_test_light_delay_hours": state["post_test_light_delay_hours"],
                "post_test_light_delay_minutes": state["post_test_light_delay_minutes"],
                "post_test_light_status": state["post_test_light_status"],
                "post_test_light_remaining_seconds": state["post_test_light_remaining_seconds"],
                "server_time": datetime.now().strftime("%d/%m/%y %H:%M:%S"),
            }
        )


@atexit.register
def _shutdown():
    scheduler_cancel.set()
    cancel_post_test_timer()
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

    ensure_startup_light_on()

    if os.getenv("AUTO_OPEN_BROWSER", "0") in {"1", "true", "True"}:
        timer = threading.Timer(1.5, lambda: webbrowser.open(f"http://{config.HOST}:{config.PORT}/"))
        timer.daemon = True
        timer.start()

    app.run(host=config.HOST, port=config.PORT)
