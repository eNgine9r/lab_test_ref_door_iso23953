"""RS-485 / Modbus RTU probe for Raspberry Pi bring-up.

The probe treats a Modbus *exception response* (e.g. illegal function/address)
as a valid communication signal (device is reachable on bus), not as link failure.
"""

import argparse
import json
import time
from dataclasses import asdict, dataclass

from pymodbus.client import ModbusSerialClient


@dataclass
class ProbeResult:
    port: str
    slave: int
    connected: bool
    modbus_ok: bool
    message: str


def candidate_ports() -> list[str]:
    try:
        from serial.tools import list_ports

        ports = [p.device for p in list_ports.comports()]
    except Exception:  # noqa: BLE001
        ports = []
    preferred = [p for p in ports if any(k in p for k in ("ttyUSB", "ttyACM", "ttyAMA", "ttyS"))]
    return preferred or ports


def _response_means_reachable(resp) -> tuple[bool, str]:
    if resp is None:
        return False, "no response"

    # Normal response -> reachable and function supported.
    if hasattr(resp, "isError") and not resp.isError():
        return True, "OK"

    # Exception response still means the slave answered on the bus.
    # For link bring-up this is enough to mark connectivity as OK.
    exc_code = getattr(resp, "exception_code", None)
    if exc_code is not None:
        return True, f"reachable (exception_code={exc_code})"

    return False, f"modbus error: {resp}"


def _try_read_methods(client: ModbusSerialClient, slave: int):
    methods = [
        lambda: client.read_coils(0, 1, slave=slave),
        lambda: client.read_discrete_inputs(0, 1, slave=slave),
        lambda: client.read_holding_registers(0, 1, slave=slave),
        lambda: client.read_input_registers(0, 1, slave=slave),
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
        return ProbeResult(port=port, slave=slave, connected=False, modbus_ok=False, message="serial connect failed")

    try:
        for attempt in range(1, retries + 1):
            ok, msg = _try_read_methods(client, slave)
            if ok:
                return ProbeResult(port=port, slave=slave, connected=True, modbus_ok=True, message=msg)
            time.sleep(0.15)
        return ProbeResult(port=port, slave=slave, connected=True, modbus_ok=False, message=msg)
    finally:
        client.close()


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
        print(json.dumps({"ok": False, "reason": "no serial ports detected"}, ensure_ascii=False))
        raise SystemExit(2)

    slave_ids = [args.slave] if args.slave > 0 else list(range(1, 11))

    results = []
    for port in ports:
        for slave in slave_ids:
            result = probe_port(
                port=port,
                slave=slave,
                baudrate=args.baudrate,
                timeout=args.timeout,
                retries=args.retries,
            )
            results.append(asdict(result))
            if result.modbus_ok:
                print(json.dumps({"ok": True, "results": results}, indent=2, ensure_ascii=False))
                raise SystemExit(0)

    print(json.dumps({"ok": False, "results": results}, indent=2, ensure_ascii=False))
    raise SystemExit(1)


if __name__ == "__main__":
    main()
