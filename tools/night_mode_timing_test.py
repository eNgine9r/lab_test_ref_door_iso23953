#!/usr/bin/env python3
import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from test_logic import ISO23953DoorTest


class FakeRelay:
    def __init__(self, now_fn):
        self.now_fn = now_fn
        self.open_events = []
        self.close_events = []

    def open_relay(self, channel: int):
        self.open_events.append((self.now_fn(), channel))

    def close_relay(self, channel: int):
        self.close_events.append((self.now_fn(), channel))

    def close_all_relays(self):
        pass

    def set_light(self, _enabled: bool):
        pass

    def reconnect(self):
        return True


class FakeLogger:
    def __init__(self):
        self.entries = []

    def info(self, msg, *args):
        text = msg % args if args else msg
        self.entries.append(text)

    def warning(self, msg, *args):
        text = msg % args if args else msg
        self.entries.append(text)

    def error(self, msg, *args):
        text = msg % args if args else msg
        self.entries.append(text)


def run_scenario():
    virtual_clock = {'mono': 0.0}

    def monotonic_now():
        return virtual_clock['mono']

    config = {
        'mode': 'MT',
        'doors': 4,
        'test_duration_hours': 12,
        'debug': False,
        'door_open_time_sec': 0.5,
        'door_close_time_sec': 0.5,
        'test_start_time_iso': '2026-04-15T09:05:00+00:00',
    }

    logger = FakeLogger()
    relay = FakeRelay(monotonic_now)
    test = ISO23953DoorTest(config, relay, logger, register_signals=False)

    def fast_sleep(seconds: float, step: float = 0.2):
        del step
        virtual_clock['mono'] += max(0.0, float(seconds))
        return test.running

    test._sleep_with_checks = fast_sleep

    with patch('test_logic.time.monotonic', side_effect=monotonic_now):
        test.run()

    day_duration_scaled = 12 * 3600
    expected_deadline_mono = day_duration_scaled
    late_opens = [evt for evt in relay.open_events if evt[0] > expected_deadline_mono + 1e-9]

    transition_logs = []
    for entry in logger.entries:
        try:
            payload = json.loads(entry)
            if payload.get('event') == 'mode_transition':
                transition_logs.append(payload)
        except Exception:
            continue

    if not transition_logs:
        raise AssertionError('mode_transition log not found')

    transition = transition_logs[-1]
    expected_night = datetime.fromisoformat('2026-04-15T21:05:00+00:00')
    calculated_night = datetime.fromisoformat(transition['calculatedNightModeTime'])

    if calculated_night != expected_night:
        raise AssertionError(f'calculatedNightModeTime mismatch: {calculated_night} != {expected_night}')

    if late_opens:
        raise AssertionError(f'door open detected after deadline: {late_opens[:3]}')

    print('OK: scenario 09:05 -> 21:05 passed; no door opens after night deadline')


if __name__ == '__main__':
    run_scenario()
