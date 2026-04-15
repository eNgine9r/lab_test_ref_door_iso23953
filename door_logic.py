import threading
import time
from datetime import datetime
from typing import Callable, Dict


class DoorLogic:
    def __init__(self, relay_controller, logger, showcase_type: str = "medium temperature"):
        self.controller = relay_controller
        self.logger = logger
        self.showcase_type = showcase_type
        self._lock = threading.Lock()
        self._door_state = {f"door{i+1}": "closed" for i in range(6)}
        self._profiles: Dict[str, Dict[str, float]] = {
            "medium temperature": {"open_multiplier": 1.0, "delay_multiplier": 1.0},
            "low temperature": {"open_multiplier": 1.2, "delay_multiplier": 1.3},
        }

    def get_states(self):
        with self._lock:
            return dict(self._door_state)

    def open_door(self, door: int, on_transition: Callable[[int, str, str], None] | None = None):
        with self._lock:
            self.controller.relay_on(door)
            self._door_state[f"door{door+1}"] = "open"
            ts = datetime.now().isoformat(timespec="seconds")
            self.logger(f"door{door+1} open", "OK")
            if on_transition:
                on_transition(door, "open", ts)

    def close_door(self, door: int, on_transition: Callable[[int, str, str], None] | None = None):
        with self._lock:
            self.controller.relay_off(door)
            self._door_state[f"door{door+1}"] = "closed"
            ts = datetime.now().isoformat(timespec="seconds")
            self.logger(f"door{door+1} close", "OK")
            if on_transition:
                on_transition(door, "close", ts)

    def safe_shutdown(self, active_doors: int = 6):
        with self._lock:
            for door in range(active_doors):
                self.controller.relay_off(door)
                self._door_state[f"door{door+1}"] = "closed"
        self.logger("safe shutdown relays", "OK")

    def test_cycle(
        self,
        door: int,
        open_time: float,
        delay: float,
        tick: Callable[[], None] | None = None,
        cycle_warning: Callable[[str], None] | None = None,
        on_transition: Callable[[int, str, str], None] | None = None,
    ):
        profile = self._profiles.get(self.showcase_type, self._profiles["medium temperature"])
        expected = (open_time * profile["open_multiplier"]) + (delay * profile["delay_multiplier"])
        start = time.monotonic()

        self.open_door(door, on_transition=on_transition)
        time.sleep(open_time * profile["open_multiplier"])
        if tick:
            tick()
        self.close_door(door, on_transition=on_transition)
        time.sleep(delay * profile["delay_multiplier"])
        if tick:
            tick()

        elapsed = time.monotonic() - start
        if elapsed > expected + 1 and cycle_warning:
            cycle_warning(f"door{door+1} cycle timing exceeded")
