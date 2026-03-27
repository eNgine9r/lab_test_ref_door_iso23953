import json
import os
import signal
import threading
import time


class ISO23953DoorTest:
    MODES = {
        'LT': {'hold_time': 6, 'cycles_per_hour': 6},
        'MT': {'hold_time': 15, 'cycles_per_hour': 10},
    }
    STARTUP_OPEN_SECONDS = 180
    STARTUP_STABILIZE_SECONDS = 300

    def __init__(self, config: dict, relay_controller, logger, register_signals: bool = True):
        self.config = config
        self.relay = relay_controller
        self.logger = logger
        self.running = True
        self.stopped_early = False
        self._register_signals = register_signals and threading.current_thread() is threading.main_thread()
        if self._register_signals:
            signal.signal(signal.SIGINT, self._handle_interrupt)
            signal.signal(signal.SIGTERM, self._handle_interrupt)

    def _handle_interrupt(self, signum, _frame):
        self.stop(f'received signal {signum}, emergency stop')

    def stop(self, reason: str = 'stop requested'):
        self.logger.warning(reason)
        self.running = False
        self.stopped_early = True
        self.relay.close_all_relays()

    def _scale(self, seconds: float) -> float:
        return seconds / 10 if self.config.get('debug') else seconds

    def _door_open_move_time(self) -> float:
        cfg = self.config.get('door_open_time_sec')
        if cfg is None:
            cfg = os.getenv('DOOR_OPEN_TIME_SEC', '0.5')
        return max(0.0, self._scale(float(cfg)))

    def _door_close_move_time(self) -> float:
        cfg = self.config.get('door_close_time_sec')
        if cfg is None:
            cfg = os.getenv('DOOR_CLOSE_TIME_SEC', '0.5')
        return max(0.0, self._scale(float(cfg)))

    def _sleep_with_checks(self, seconds: float, step: float = 0.2):
        remaining = max(0.0, float(seconds))
        while self.running and remaining > 0:
            pause = min(step, remaining)
            time.sleep(pause)
            remaining -= pause
        return self.running

    def _with_reconnect(self, fn, description: str):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            self.logger.error('%s failed: %s', description, exc)
            time.sleep(1)
            if self.relay.reconnect():
                self.logger.info('reconnected after failure: %s', description)
                return fn()
            self.logger.error('reconnect failed after: %s', description)
            raise

    def startup_phase(self, doors: int):
        self.logger.info('startup phase begin')
        for door in range(1, doors + 1):
            if not self.running:
                return
            self._with_reconnect(lambda d=door: self.relay.open_relay(d), f'open door {door} in startup')
            self.logger.info('startup door %s opened for load phase', door)
            if not self._sleep_with_checks(self._scale(self.STARTUP_OPEN_SECONDS)):
                return
            self._with_reconnect(lambda d=door: self.relay.close_relay(d), f'close door {door} in startup')
            self.logger.info('startup door %s closed after load phase', door)
        if self.running:
            self.logger.info('startup stabilization begin')
            self._sleep_with_checks(self._scale(self.STARTUP_STABILIZE_SECONDS))
        self.logger.info('startup phase end')

    def main_test(self, doors: int, hours: int, mode: str):
        profile = self.MODES[mode]
        hold_time = self._scale(profile['hold_time'])
        move_open_time = self._door_open_move_time()
        move_close_time = self._door_close_move_time()
        cycles_per_hour = profile['cycles_per_hour']

        interval = self._scale(3600 / cycles_per_hour)
        door_action_time = hold_time + move_open_time + move_close_time
        remaining_interval = max(0.0, interval - door_action_time)
        inter_door_delay = remaining_interval / max(1, doors)

        self.logger.info(
            'main test start mode=%s doors=%s hours=%s hold_time=%.2f move_open=%.2f move_close=%.2f interval=%.2f inter_door_delay=%.2f',
            mode,
            doors,
            hours,
            hold_time,
            move_open_time,
            move_close_time,
            interval,
            inter_door_delay,
        )

        self._with_reconnect(lambda: self.relay.set_light(True), 'turn light ON for day mode')

        for hour in range(hours):
            if not self.running:
                break
            self.logger.info('test hour %s/%s', hour + 1, hours)
            for cycle in range(cycles_per_hour):
                if not self.running:
                    break
                self.logger.info('cycle %s/%s in hour %s', cycle + 1, cycles_per_hour, hour + 1)
                for door in range(1, doors + 1):
                    if not self.running:
                        break

                    self._with_reconnect(lambda d=door: self.relay.open_relay(d), f'open door {door}')
                    self.logger.info('door %s opening started', door)
                    if not self._sleep_with_checks(move_open_time):
                        break

                    self.logger.info('door %s fully opened; hold phase start', door)
                    if not self._sleep_with_checks(hold_time):
                        break

                    self._with_reconnect(lambda d=door: self.relay.close_relay(d), f'close door {door}')
                    self.logger.info('door %s closing started', door)
                    if not self._sleep_with_checks(move_close_time):
                        break

                    total_cycle_time = move_open_time + hold_time + move_close_time
                    self.logger.info(
                        '%s',
                        json.dumps(
                            {
                                'event': 'door_cycle',
                                'door': door,
                                'open_time': move_open_time,
                                'hold_time': hold_time,
                                'close_time': move_close_time,
                                'total_cycle_time': total_cycle_time,
                            },
                            ensure_ascii=False,
                        ),
                    )

                    if hasattr(self.relay, 'record_cycle'):
                        self.relay.record_cycle(door)
                    if not self._sleep_with_checks(inter_door_delay):
                        break

        self.logger.info('main test end')

    def night_mode(self):
        self.logger.info('night mode start')
        self._with_reconnect(lambda: self.relay.set_light(False), 'turn light OFF for night mode')
        self.relay.close_all_relays()
        self.logger.info('night mode end')

    def run(self):
        mode = self.config.get('mode', 'LT').upper()
        doors = max(1, min(5, int(self.config.get('doors', 1))))
        hours = int(self.config.get('test_duration_hours', 12))

        if mode not in self.MODES:
            raise ValueError(f'Unsupported mode: {mode}')

        self.startup_phase(doors)
        if self.running:
            self.main_test(doors, hours, mode)
        self.night_mode()
