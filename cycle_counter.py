import json
import threading
from pathlib import Path
from typing import Dict


class CycleCounter:
    def __init__(self, file_path: Path, doors: int = 4):
        self.file_path = Path(file_path)
        self._lock = threading.Lock()
        self._doors = doors
        self._cycles = {f"door{i+1}": 0 for i in range(doors)}
        self._load()

    def _load(self):
        if self.file_path.exists():
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            for k in self._cycles:
                self._cycles[k] = int(data.get(k, 0))
        else:
            self.save_cycles()

    def add_cycle(self, door: int):
        key = f"door{door+1}"
        with self._lock:
            self._cycles[key] += 1
            self.save_cycles()

    def get_cycles(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._cycles)

    def reset(self):
        with self._lock:
            for key in self._cycles:
                self._cycles[key] = 0
            self.save_cycles()

    def save_cycles(self):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(json.dumps(self._cycles, indent=2), encoding="utf-8")
