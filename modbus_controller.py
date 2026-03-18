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
        self._instrument = None
        self._port = MODBUS_PORT
        self._lock = threading.Lock()
        self._backend = os.getenv("MODBUS_BACKEND", "auto")

    @staticmethod
    def detect_serial_ports() -> List[str]:
        ports = [p.device for p in list_ports.comports()]
        usb_first = [p for p in ports if any(token in p for token in ("ttyUSB", "ttyACM"))]
        uart_next = [p for p in ports if p not in usb_first and any(token in p for token in ("ttyAMA", "ttyS"))]
        ordered = usb_first + uart_next
        if MODBUS_PORT and MODBUS_PORT not in ordered:
            ordered.insert(0, MODBUS_PORT)
        return ordered or ports

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
    def _device_arg(method, slave_id: int) -> dict:
        params = inspect.signature(method).parameters
        if "device_id" in params:
            return {"device_id": slave_id}
        if "unit" in params:
            return {"unit": slave_id}
        if "slave" in params:
            return {"slave": slave_id}
        return {"slave": slave_id}

    @staticmethod
    def _build_instrument(port: str):
        import minimalmodbus

        instrument = minimalmodbus.Instrument(port, MODBUS_SLAVE_ID)
        instrument.serial.baudrate = MODBUS_BAUDRATE
        instrument.serial.bytesize = MODBUS_BYTESIZE
        instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
        instrument.serial.stopbits = MODBUS_STOPBITS
        instrument.serial.timeout = 1
        return instrument

    def _connect_pymodbus(self, port: str) -> bool:
        client = self._build_client(port)
        if client.connect():
            self._client = client
            self._instrument = None
            self._port = port
            self._backend = "pymodbus"
            return True
        return False

    def _connect_minimalmodbus(self, port: str) -> bool:
        instrument = self._build_instrument(port)
        try:
            instrument.read_bits(0, 1)
            self._instrument = instrument
            self._client = None
            self._port = port
            self._backend = "minimalmodbus"
            return True
        except Exception:  # noqa: BLE001
            return False

    def connect(self) -> bool:
        with self._lock:
            ports = [MODBUS_PORT]
            if os.getenv("MODBUS_AUTODETECT", "1") in {"1", "true", "True"}:
                ports = self.detect_serial_ports()

            requested_backend = os.getenv("MODBUS_BACKEND", self._backend)
            for port in ports:
                if requested_backend in {"pymodbus", "auto"} and self._connect_pymodbus(port):
                    return True
                if requested_backend in {"minimalmodbus", "auto"} and self._connect_minimalmodbus(port):
                    return True

            self._client = None
            self._instrument = None
            return False

    def close(self):
        with self._lock:
            if self._client:
                self._client.close()
                self._client = None
            if self._instrument:
                try:
                    self._instrument.serial.close()
                except Exception:  # noqa: BLE001
                    pass
                self._instrument = None

    def active_port(self) -> str:
        return self._port

    def active_backend(self) -> str:
        return self._backend

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
            if self._backend == "minimalmodbus":
                if not self._instrument:
                    raise RuntimeError("MinimalModbus instrument is not connected")
                self._retry(lambda: self._instrument.write_bit(channel, 1 if value else 0))
                return True

            if not self._client:
                raise RuntimeError("Modbus client is not connected")
            args = self._device_arg(self._client.write_coil, MODBUS_SLAVE_ID)
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
            if self._backend == "minimalmodbus":
                if not self._instrument:
                    raise RuntimeError("MinimalModbus instrument is not connected")
                bits = self._retry(lambda: self._instrument.read_bits(0, count))
                return [bool(bit) for bit in bits[:count]]

            if not self._client:
                raise RuntimeError("Modbus client is not connected")
            args = self._device_arg(self._client.read_coils, MODBUS_SLAVE_ID)
            rr = self._retry(lambda: self._client.read_coils(0, count, **args))
        return list(rr.bits[:count])

    def ping(self) -> bool:
        if self._backend == "minimalmodbus":
            try:
                self.read_inputs(1)
                return True
            except Exception:  # noqa: BLE001
                return False

        if not self._client:
            return False

        methods = [
            lambda: self._client.read_coils(0, 1, **self._device_arg(self._client.read_coils, MODBUS_SLAVE_ID)),
            lambda: self._client.read_discrete_inputs(0, 1, **self._device_arg(self._client.read_discrete_inputs, MODBUS_SLAVE_ID)),
            lambda: self._client.read_holding_registers(0, 1, **self._device_arg(self._client.read_holding_registers, MODBUS_SLAVE_ID)),
            lambda: self._client.read_input_registers(0, 1, **self._device_arg(self._client.read_input_registers, MODBUS_SLAVE_ID)),
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
