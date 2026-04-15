import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "0") in {"1", "true", "True"}

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))

MODBUS_PORT = os.getenv("MODBUS_PORT", "/dev/ttyUSB0")
MODBUS_BAUDRATE = int(os.getenv("MODBUS_BAUDRATE", "9600"))
MODBUS_PARITY = os.getenv("MODBUS_PARITY", "N")
MODBUS_STOPBITS = int(os.getenv("MODBUS_STOPBITS", "1"))
MODBUS_BYTESIZE = int(os.getenv("MODBUS_BYTESIZE", "8"))
MODBUS_SLAVE_ID = int(os.getenv("MODBUS_SLAVE_ID", "1"))

DOOR_COUNT = int(os.getenv("DOOR_COUNT", "4"))
MAX_DOORS = 6
WATCHDOG_TIMEOUT = int(os.getenv("WATCHDOG_TIMEOUT", "10"))
RECONNECT_INTERVAL = int(os.getenv("RECONNECT_INTERVAL", "5"))
RETRY_LIMIT = int(os.getenv("RETRY_LIMIT", "3"))

CYCLES_FILE = DATA_DIR / "cycles.json"
LOG_FILE = LOG_DIR / "system.log"

DEFAULT_OPEN_TIME = float(os.getenv("DEFAULT_OPEN_TIME", "2"))
DEFAULT_DELAY = float(os.getenv("DEFAULT_DELAY", "1"))
SHOWCASE_TYPE = os.getenv("SHOWCASE_TYPE", "medium temperature")

LIGHT_RELAY_CHANNEL = int(os.getenv("LIGHT_RELAY_CHANNEL", "5"))

MODBUS_AUTODETECT = os.getenv("MODBUS_AUTODETECT", "1") in {"1", "true", "True"}
