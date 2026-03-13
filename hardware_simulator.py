import threading


class HardwareSimulator:
    """In-memory relay/door state simulator for demo and CI runs."""

    def __init__(self, channels: int = 8):
        self.relays = [False] * channels
        self._lock = threading.Lock()

    def connect(self) -> bool:
        return True

    def close(self) -> None:
        self.all_off()

    def relay_on(self, channel: int) -> bool:
        with self._lock:
            self.relays[channel] = True
        return True

    def relay_off(self, channel: int) -> bool:
        with self._lock:
            self.relays[channel] = False
        return True

    def all_off(self) -> None:
        with self._lock:
            for i in range(len(self.relays)):
                self.relays[i] = False

    def write_coil(self, channel: int, value: bool) -> bool:
        return self.relay_on(channel) if value else self.relay_off(channel)

    def read_inputs(self):
        with self._lock:
            return list(self.relays)

    def ping(self) -> bool:
        return True
