"""RS-485 / Modbus RTU probe for Raspberry Pi bring-up."""

import argparse
import json
from dataclasses import asdict, dataclass

from pymodbus.client import ModbusSerialClient
from serial.tools import list_ports


@dataclass
class ProbeResult:
    port: str
    connected: bool
    modbus_ok: bool
    message: str


def candidate_ports() -> list[str]:
    ports = [p.device for p in list_ports.comports()]
    preferred = [p for p in ports if any(k in p for k in ("ttyUSB", "ttyACM", "ttyAMA", "ttyS"))]
    return preferred or ports


def probe_port(port: str, slave: int, baudrate: int, timeout: float) -> ProbeResult:
    client = ModbusSerialClient(
        port=port,
        baudrate=baudrate,
        parity="N",
        stopbits=1,
        bytesize=8,
        timeout=timeout,
    )
    if not client.connect():
        return ProbeResult(port=port, connected=False, modbus_ok=False, message="serial connect failed")

    try:
        rr = client.read_coils(0, 1, slave=slave)
        if rr is None or rr.isError():
            return ProbeResult(port=port, connected=True, modbus_ok=False, message=f"modbus error: {rr}")
        return ProbeResult(port=port, connected=True, modbus_ok=True, message="OK")
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(port=port, connected=True, modbus_ok=False, message=f"exception: {exc}")
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="", help="Explicit serial port, e.g. /dev/ttyUSB0")
    parser.add_argument("--slave", type=int, default=1)
    parser.add_argument("--baudrate", type=int, default=9600)
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args()

    ports = [args.port] if args.port else candidate_ports()
    if not ports:
        print(json.dumps({"ok": False, "reason": "no serial ports detected"}, ensure_ascii=False))
        raise SystemExit(2)

    results = [asdict(probe_port(port, args.slave, args.baudrate, args.timeout)) for port in ports]
    ok = any(r["modbus_ok"] for r in results)
    print(json.dumps({"ok": ok, "results": results}, indent=2, ensure_ascii=False))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
