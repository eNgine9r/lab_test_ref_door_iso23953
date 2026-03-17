import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class CycleCounter:
    def __init__(self, file_path: Path, doors: int = 6):
        self.file_path = Path(file_path)
        self._lock = threading.Lock()
        self._doors = doors
        self._cycles = {f"door{i+1}": 0 for i in range(doors)}
        self._events: List[Dict[str, str]] = []
        self._max_events = 1000
        self._load()

    def _load(self):
        if self.file_path.exists():
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "cycles" in data:
                cycles_data = data.get("cycles", {})
                events_data = data.get("events", [])
            else:
                cycles_data = data
                events_data = []

            for k in self._cycles:
                self._cycles[k] = int(cycles_data.get(k, 0))
            self._events = [e for e in events_data if isinstance(e, dict)][-self._max_events :]
        else:
            self.save_cycles()

    def add_cycle(self, door: int):
        key = f"door{door+1}"
        with self._lock:
            self._cycles[key] += 1
            self.save_cycles()

    def add_transition_event(self, door: int, action: str, event_time: str | None = None):
        with self._lock:
            self._events.append(
                {
                    "timestamp": event_time or datetime.now().isoformat(timespec="seconds"),
                    "door": f"door{door+1}",
                    "action": action,
                }
            )
            self._events = self._events[-self._max_events :]
            self.save_cycles()

    def get_cycles(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._cycles)

    def get_events(self, limit: int = 200) -> List[Dict[str, str]]:
        with self._lock:
            return list(self._events[-limit:])

    def reset(self):
        with self._lock:
            for key in self._cycles:
                self._cycles[key] = 0
            self._events = []
            self.save_cycles()

    def save_cycles(self):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cycles": self._cycles,
            "events": self._events,
        }
        self.file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
