from datetime import datetime, timedelta
import time


class StartScheduler:
    def __init__(self, logger):
        self.logger = logger

    def apply_start_delay(self, delay_seconds: int):
        if delay_seconds > 0:
            self.logger.info('start delay %s sec', delay_seconds)
            time.sleep(delay_seconds)

    def wait_for_schedule(self, enabled: bool, start_time: str):
        if not enabled:
            return

        now = datetime.now()
        hour, minute = map(int, start_time.split(':', 1))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        self.logger.info('scheduled start at %s, waiting %.0f sec', target.isoformat(), wait_seconds)
        time.sleep(wait_seconds)
