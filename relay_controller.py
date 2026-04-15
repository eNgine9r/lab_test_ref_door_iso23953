import time


class RelayController:
    DOOR_CHANNELS = [1, 2, 3, 4, 5]
    LIGHT_CHANNEL = 6

    def __init__(self, controller, logger):
        self.controller = controller
        self.logger = logger

    def connect(self) -> bool:
        return self.controller.connect()

    def reconnect(self) -> bool:
        self.logger.info('attempt reconnect to modbus backend')
        try:
            self.controller.close()
        except Exception:  # noqa: BLE001
            pass
        return self.controller.connect()

    def open_relay(self, channel: int):
        self.controller.relay_on(channel - 1)
        self.logger.info('relay %s ON', channel)

    def close_relay(self, channel: int):
        self.controller.relay_off(channel - 1)
        self.logger.info('relay %s OFF', channel)

    def close_all_relays(self):
        for channel in self.DOOR_CHANNELS + [self.LIGHT_CHANNEL]:
            try:
                self.close_relay(channel)
            except Exception as exc:  # noqa: BLE001
                self.logger.error('close relay %s failed: %s', channel, exc)

    def set_light(self, enabled: bool):
        if enabled:
            self.open_relay(self.LIGHT_CHANNEL)
        else:
            self.close_relay(self.LIGHT_CHANNEL)

    def safe_pause(self, seconds: float):
        time.sleep(max(0, seconds))
