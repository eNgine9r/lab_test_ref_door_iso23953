import os
import threading
from typing import List

from pymodbus.client import ModbusSerialClient
from serial.tools import list_ports

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
        self._client = None
        self._port = MODBUS_PORT
        self._lock = threading.Lock()

    @staticmethod
    def detect_serial_ports() -> List[str]:
        ports = [p.device for p in list_ports.comports()]
        preferred = [
            p
            for p in ports
            if any(token in p for token in ("ttyUSB", "ttyACM", "ttyAMA", "ttyS"))
        ]
        if MODBUS_PORT and MODBUS_PORT not in preferred:
            preferred.insert(0, MODBUS_PORT)
        return preferred or ports

    def _build_client(self, port: str) -> ModbusSerialClient:
        return ModbusSerialClient(
            port=port,
            baudrate=MODBUS_BAUDRATE,
            parity=MODBUS_PARITY,
            stopbits=MODBUS_STOPBITS,
            bytesize=MODBUS_BYTESIZE,
            timeout=1,
        )

    def connect(self) -> bool:
        with self._lock:
            ports = [MODBUS_PORT]
            if os.getenv("MODBUS_AUTODETECT", "1") in {"1", "true", "True"}:
                ports = self.detect_serial_ports()

            for port in ports:
                client = self._build_client(port)
                if client.connect():
                    self._client = client
                    self._port = port
                    return True
            self._client = None
            return False

    def close(self):
        with self._lock:
            if self._client:
                self._client.close()
                self._client = None

    def active_port(self) -> str:
        return self._port

    def _retry(self, fn):
        if not self._client:
            raise RuntimeError("Modbus client is not connected")

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
