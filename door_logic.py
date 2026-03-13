import threading
import time
from typing import Callable, Dict


class DoorLogic:
    def __init__(self, relay_controller, logger, showcase_type: str = "medium temperature"):
        self.controller = relay_controller
        self.logger = logger
        self.showcase_type = showcase_type
        self._lock = threading.Lock()
        self._door_state = {f"door{i+1}": "closed" for i in range(8)}
        self._profiles: Dict[str, Dict[str, float]] = {
            "medium temperature": {"open_multiplier": 1.0, "delay_multiplier": 1.0},
            "low temperature": {"open_multiplier": 1.2, "delay_multiplier": 1.3},
        }

    def get_states(self):
        with self._lock:
            return dict(self._door_state)

    def open_door(self, door: int):
        with self._lock:
            self.controller.relay_on(door)
            self._door_state[f"door{door+1}"] = "open"
            self.logger(f"door{door+1} open", "OK")

    def close_door(self, door: int):
        with self._lock:
            self.controller.relay_off(door)
            self._door_state[f"door{door+1}"] = "closed"
            self.logger(f"door{door+1} close", "OK")

    def safe_shutdown(self, active_doors: int = 4):
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
    ):
        profile = self._profiles.get(self.showcase_type, self._profiles["medium temperature"])
        expected = (open_time * profile["open_multiplier"]) + (delay * profile["delay_multiplier"])
        start = time.monotonic()

        self.open_door(door)
        time.sleep(open_time * profile["open_multiplier"])
        if tick:
            tick()
        self.close_door(door)
        time.sleep(delay * profile["delay_multiplier"])
        if tick:
            tick()

        elapsed = time.monotonic() - start
        if elapsed > expected + 1 and cycle_warning:
            cycle_warning(f"door{door+1} cycle timing exceeded")
