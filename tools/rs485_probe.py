"""RS-485 / Modbus RTU probe for Raspberry Pi bring-up.

Probe order:
1. pymodbus with compatibility for device_id/unit/slave
2. minimalmodbus fallback

This avoids false negatives when pymodbus API or framing differs while the bus is
actually working, as confirmed by minimalmodbus.
"""

import argparse
import inspect
import json
import time
from dataclasses import asdict, dataclass

import minimalmodbus
from pymodbus import __version__ as PYMODBUS_VERSION
from pymodbus.client import ModbusSerialClient
from serial.tools import list_ports


@dataclass
class ProbeResult:
    port: str
    slave: int
    connected: bool
    modbus_ok: bool
    backend: str
    message: str


def candidate_ports() -> list[str]:
    ports = [p.device for p in list_ports.comports()]
    usb_first = [p for p in ports if any(k in p for k in ("ttyUSB", "ttyACM"))]
    uart_next = [p for p in ports if p not in usb_first and any(k in p for k in ("ttyAMA", "ttyS"))]
    return usb_first + uart_next or ports


def device_arg(method, slave_id: int) -> dict:
    params = inspect.signature(method).parameters
    if "device_id" in params:
        return {"device_id": slave_id}
    if "unit" in params:
        return {"unit": slave_id}
    if "slave" in params:
        return {"slave": slave_id}
    return {"slave": slave_id}


def _response_means_reachable(resp) -> tuple[bool, str]:
    if resp is None:
        return False, "no response"
    if hasattr(resp, "isError") and not resp.isError():
        return True, "OK via pymodbus"
    exc_code = getattr(resp, "exception_code", None)
    if exc_code is not None:
        return True, f"reachable via pymodbus (exception_code={exc_code})"
    return False, f"modbus error: {resp}"


def _try_pymodbus_methods(client: ModbusSerialClient, slave_id: int):
    methods = [
        lambda: client.read_coils(0, 1, **device_arg(client.read_coils, slave_id)),
        lambda: client.read_discrete_inputs(0, 1, **device_arg(client.read_discrete_inputs, slave_id)),
        lambda: client.read_holding_registers(0, 1, **device_arg(client.read_holding_registers, slave_id)),
        lambda: client.read_input_registers(0, 1, **device_arg(client.read_input_registers, slave_id)),
    ]
    last_msg = "no response"
    for method in methods:
        try:
            resp = method()
            ok, msg = _response_means_reachable(resp)
            if ok:
                return True, msg
            last_msg = msg
        except Exception as exc:  # noqa: BLE001
            last_msg = f"exception: {exc}"
    return False, last_msg


def _try_minimalmodbus(port: str, slave_id: int) -> tuple[bool, str]:
    instrument = minimalmodbus.Instrument(port, slave_id)
    instrument.serial.baudrate = 9600
    instrument.serial.bytesize = 8
    instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
    instrument.serial.stopbits = 1
    instrument.serial.timeout = 1
    try:
        bits = instrument.read_bits(0, 1)
        return True, f"OK via minimalmodbus bits={bits}"
    except Exception as exc:  # noqa: BLE001
        return False, f"minimalmodbus error: {exc}"
    finally:
        instrument.serial.close()


def probe_port(port: str, slave: int, baudrate: int, timeout: float, retries: int) -> ProbeResult:
    client = ModbusSerialClient(
        port=port,
        baudrate=baudrate,
        parity="N",
        stopbits=1,
        bytesize=8,
        timeout=timeout,
    )
    if not client.connect():
        return ProbeResult(port=port, slave=slave, connected=False, modbus_ok=False, backend="none", message="serial connect failed")

    try:
        message = "no response"
        for _ in range(retries):
            ok, message = _try_pymodbus_methods(client, slave)
            if ok:
                return ProbeResult(port=port, slave=slave, connected=True, modbus_ok=True, backend="pymodbus", message=message)
            time.sleep(0.15)
    finally:
        client.close()

    ok, fallback_message = _try_minimalmodbus(port, slave)
    if ok:
        return ProbeResult(port=port, slave=slave, connected=True, modbus_ok=True, backend="minimalmodbus", message=fallback_message)
    return ProbeResult(port=port, slave=slave, connected=True, modbus_ok=False, backend="none", message=f"{message}; {fallback_message}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="", help="Explicit serial port, e.g. /dev/ttyUSB0")
    parser.add_argument("--slave", type=int, default=1, help="Use 0 to scan slave ids 1..10")
    parser.add_argument("--baudrate", type=int, default=9600)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    ports = [args.port] if args.port else candidate_ports()
    if not ports:
        print(json.dumps({"ok": False, "reason": "no serial ports detected", "pymodbus_version": PYMODBUS_VERSION}, ensure_ascii=False))
        raise SystemExit(2)

    slave_ids = [args.slave] if args.slave > 0 else list(range(1, 11))

    results = []
    for port in ports:
        for slave in slave_ids:
            result = probe_port(port, slave, args.baudrate, args.timeout, args.retries)
            results.append(asdict(result))
            if result.modbus_ok:
                print(json.dumps({"ok": True, "pymodbus_version": PYMODBUS_VERSION, "results": results}, indent=2, ensure_ascii=False))
                raise SystemExit(0)

    print(json.dumps({"ok": False, "pymodbus_version": PYMODBUS_VERSION, "results": results}, indent=2, ensure_ascii=False))
    raise SystemExit(1)


if __name__ == "__main__":
    main()
