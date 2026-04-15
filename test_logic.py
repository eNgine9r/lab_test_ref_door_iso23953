import json
import os
import signal
import threading
import time
from datetime import datetime, timedelta


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

    @staticmethod
    def _now_local() -> datetime:
        return datetime.now().astimezone()

    def _resolve_test_start_wall_time(self) -> datetime:
        configured_start = self.config.get('test_start_time_iso')
        if not configured_start:
            return self._now_local()
        parsed = datetime.fromisoformat(str(configured_start))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=self._now_local().tzinfo)
        return parsed.astimezone()

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

    @staticmethod
    def _seconds_until_deadline(deadline_monotonic: float) -> float:
        return max(0.0, deadline_monotonic - time.monotonic())

    def startup_phase(self, doors: int, deadline_monotonic: float):
        self.logger.info('startup phase begin')
        for door in range(1, doors + 1):
            if not self.running or self._seconds_until_deadline(deadline_monotonic) <= 0:
                return
            self._with_reconnect(lambda d=door: self.relay.open_relay(d), f'open door {door} in startup')
            self.logger.info('startup door %s opened for load phase', door)
            wait_open = min(self._scale(self.STARTUP_OPEN_SECONDS), self._seconds_until_deadline(deadline_monotonic))
            if not self._sleep_with_checks(wait_open):
                return
            self._with_reconnect(lambda d=door: self.relay.close_relay(d), f'close door {door} in startup')
            self.logger.info('startup door %s closed after load phase', door)

        if self.running and self._seconds_until_deadline(deadline_monotonic) > 0:
            self.logger.info('startup stabilization begin')
            wait_stabilize = min(self._scale(self.STARTUP_STABILIZE_SECONDS), self._seconds_until_deadline(deadline_monotonic))
            self._sleep_with_checks(wait_stabilize)
        self.logger.info('startup phase end')

    def main_test(self, doors: int, mode: str, day_deadline_monotonic: float):
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
            'main test start mode=%s doors=%s hold_time=%.2f move_open=%.2f move_close=%.2f interval=%.2f inter_door_delay=%.2f',
            mode,
            doors,
            hold_time,
            move_open_time,
            move_close_time,
            interval,
            inter_door_delay,
        )

        self._with_reconnect(lambda: self.relay.set_light(True), 'turn light ON for day mode')

        cycle_counter = 0
        while self.running and self._seconds_until_deadline(day_deadline_monotonic) > 0:
            cycle_counter += 1
            self.logger.info('day cycle %s', cycle_counter)

            for door in range(1, doors + 1):
                if not self.running or self._seconds_until_deadline(day_deadline_monotonic) <= 0:
                    break

                self._with_reconnect(lambda d=door: self.relay.open_relay(d), f'open door {door}')
                self.logger.info('door %s opening started', door)
                if not self._sleep_with_checks(min(move_open_time, self._seconds_until_deadline(day_deadline_monotonic))):
                    break

                if self._seconds_until_deadline(day_deadline_monotonic) <= 0:
                    break

                self.logger.info('door %s fully opened; hold phase start', door)
                hold_wait = min(hold_time, self._seconds_until_deadline(day_deadline_monotonic))
                if not self._sleep_with_checks(hold_wait):
                    break

                self._with_reconnect(lambda d=door: self.relay.close_relay(d), f'close door {door}')
                self.logger.info('door %s closing started', door)
                if not self._sleep_with_checks(move_close_time):
                    break

                total_cycle_time = move_open_time + hold_wait + move_close_time
                self.logger.info(
                    '%s',
                    json.dumps(
                        {
                            'event': 'door_cycle',
                            'door': door,
                            'open_time': move_open_time,
                            'hold_time': hold_wait,
                            'close_time': move_close_time,
                            'total_cycle_time': total_cycle_time,
                        },
                        ensure_ascii=False,
                    ),
                )

                if hasattr(self.relay, 'record_cycle'):
                    self.relay.record_cycle(door)

                if self._seconds_until_deadline(day_deadline_monotonic) <= 0:
                    break
                if not self._sleep_with_checks(min(inter_door_delay, self._seconds_until_deadline(day_deadline_monotonic))):
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
        day_mode_hours = float(self.config.get('test_duration_hours', 12))

        if mode not in self.MODES:
            raise ValueError(f'Unsupported mode: {mode}')

        test_start_wall_time = self._resolve_test_start_wall_time()
        day_mode_duration_sec = self._scale(day_mode_hours * 3600)
        calculated_night_mode_time = test_start_wall_time + timedelta(seconds=day_mode_duration_sec)

        monotonic_start = time.monotonic()
        day_deadline_monotonic = monotonic_start + day_mode_duration_sec

        self.logger.info(
            '%s',
            json.dumps(
                {
                    'event': 'mode_transition_plan',
                    'testStartTime': test_start_wall_time.isoformat(),
                    'calculatedNightModeTime': calculated_night_mode_time.isoformat(),
                    'actualNightModeTime': None,
                    'currentMode': 'day',
                    'reason': 'test_start',
                },
                ensure_ascii=False,
            ),
        )

        self.startup_phase(doors, day_deadline_monotonic)
        if self.running and self._seconds_until_deadline(day_deadline_monotonic) > 0:
            self.main_test(doors, mode, day_deadline_monotonic)

        actual_night_mode_time = self._now_local()
        reason = 'day_mode_duration_elapsed' if self._seconds_until_deadline(day_deadline_monotonic) <= 0 else 'stopped_early'
        self.logger.info(
            '%s',
            json.dumps(
                {
                    'event': 'mode_transition',
                    'testStartTime': test_start_wall_time.isoformat(),
                    'calculatedNightModeTime': calculated_night_mode_time.isoformat(),
                    'actualNightModeTime': actual_night_mode_time.isoformat(),
                    'currentMode': 'night',
                    'reason': reason,
                },
                ensure_ascii=False,
            ),
        )

        self.night_mode()
