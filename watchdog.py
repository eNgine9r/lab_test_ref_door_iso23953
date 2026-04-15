import threading
import time


class SystemWatchdog:
    def __init__(self, timeout: int, on_timeout):
        self.timeout = timeout
        self.on_timeout = on_timeout
        self._last_tick = time.monotonic()
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def tick(self):
        with self._lock:
            self._last_tick = time.monotonic()

    def _loop(self):
        while self._running:
            with self._lock:
                age = time.monotonic() - self._last_tick
            if age > self.timeout:
                self.on_timeout()
                with self._lock:
                    self._last_tick = time.monotonic()
            time.sleep(1)
