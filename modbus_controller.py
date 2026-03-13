import threading
from typing import List

from pymodbus.client import ModbusSerialClient

from config import (
    MODBUS_BAUDRATE,
    MODBUS_BYTESIZE,
    MODBUS_PARITY,
    MODBUS_PORT,
    MODBUS_SLAVE_ID,
    MODBUS_STOPBITS,
    RETRY_LIMIT,
)


class ModbusController:
    def __init__(self):
        self._client = ModbusSerialClient(
            port=MODBUS_PORT,
            baudrate=MODBUS_BAUDRATE,
            parity=MODBUS_PARITY,
            stopbits=MODBUS_STOPBITS,
            bytesize=MODBUS_BYTESIZE,
            timeout=1,
        )
        self._lock = threading.Lock()

    def connect(self) -> bool:
        return self._client.connect()

    def close(self):
        self._client.close()

    def _retry(self, fn):
        last_error = None
        for _ in range(RETRY_LIMIT):
            try:
                result = fn()
                if hasattr(result, "isError") and result.isError():
                    last_error = RuntimeError(str(result))
                    continue
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if last_error:
            raise last_error
        raise RuntimeError("Modbus retry failed")

    def write_coil(self, channel: int, value: bool) -> bool:
        with self._lock:
            self._retry(lambda: self._client.write_coil(channel, value, slave=MODBUS_SLAVE_ID))
        return True

    def relay_on(self, channel: int) -> bool:
        return self.write_coil(channel, True)

    def relay_off(self, channel: int) -> bool:
        return self.write_coil(channel, False)

    def all_off(self, channels: int = 8):
        for ch in range(channels):
            self.relay_off(ch)

    def read_inputs(self, count: int = 8) -> List[bool]:
        with self._lock:
            rr = self._retry(lambda: self._client.read_coils(0, count, slave=MODBUS_SLAVE_ID))
        return list(rr.bits[:count])

    def ping(self) -> bool:
        self.read_inputs(1)
        return True
