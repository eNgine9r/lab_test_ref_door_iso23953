import inspect
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

    @staticmethod
    def _device_arg(method) -> dict:
        params = inspect.signature(method).parameters
        if "unit" in params:
            return {"unit": MODBUS_SLAVE_ID}
        return {"slave": MODBUS_SLAVE_ID}

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
            args = self._device_arg(self._client.write_coil)
            self._retry(lambda: self._client.write_coil(channel, value, **args))
        return True

    def relay_on(self, channel: int) -> bool:
        return self.write_coil(channel, True)

    def relay_off(self, channel: int) -> bool:
        return self.write_coil(channel, False)

    def all_off(self, channels: int = 6):
        for ch in range(channels):
            self.relay_off(ch)

    def read_inputs(self, count: int = 6) -> List[bool]:
        with self._lock:
            args = self._device_arg(self._client.read_coils)
            rr = self._retry(lambda: self._client.read_coils(0, count, **args))
        return list(rr.bits[:count])

    def ping(self) -> bool:
        """Connectivity probe tolerant to Modbus exception responses."""
        if not self._client:
            return False

        methods = [
            lambda: self._client.read_coils(0, 1, **self._device_arg(self._client.read_coils)),
            lambda: self._client.read_discrete_inputs(0, 1, **self._device_arg(self._client.read_discrete_inputs)),
            lambda: self._client.read_holding_registers(0, 1, **self._device_arg(self._client.read_holding_registers)),
            lambda: self._client.read_input_registers(0, 1, **self._device_arg(self._client.read_input_registers)),
        ]
        for method in methods:
            try:
                resp = method()
                if resp is None:
                    continue
                if hasattr(resp, "isError") and not resp.isError():
                    return True
                if getattr(resp, "exception_code", None) is not None:
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False
