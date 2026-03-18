# Door Test Controller

Door Test Controller — Raspberry Pi система для ресурсних тестів дверей холодильних вітрин через VRC-R6 по RS-485 Modbus RTU.

## Що додано під ISO 23953-2

Додано окремий production-сценарій запуску за ТЗ:

- `main.py` — головна точка запуску тесту
- `config.json` — конфігурація тесту
- `modbus_client.py` — фабрика backend-контролера
- `relay_controller.py` — API реле `open_relay/close_relay/close_all_relays`
- `scheduler.py` — відкладений та scheduled старт
- `test_logic.py` — логіка циклів ISO 23953-2
- `logger.py` — логування в `logs/test.log`

## Логіка тесту

### 1. Startup / імітація завантаження

- Відкрити всі двері → 180 сек
- Закрити всі двері → 300 сек

### 2. Основний тест

Для `LT`:
- `open_time = 6 sec`
- `cycles_per_hour = 6`

Для `MT`:
- `open_time = 15 sec`
- `cycles_per_hour = 10`

Розрахунок:

- `interval = 3600 / cycles_per_hour`
- `close_time = interval - open_time`
- двері відкриваються **послідовно**, не одночасно
- підтримується `1..5` дверей

### 3. Night mode

- реле 6 (`Light`) вимикається
- усі двері закриті
- нові відкриття не виконуються

### 4. Debug mode

Якщо `debug=true`, усі таймінги діляться на 10.

## Mapping реле VRC-R6

- Relay 1 → Door 1
- Relay 2 → Door 2
- Relay 3 → Door 3
- Relay 4 → Door 4
- Relay 5 → Door 5
- Relay 6 → Light

## Конфігурація `config.json`

```json
{
  "mode": "LT",
  "doors": 3,
  "test_duration_hours": 12,
  "start_delay_sec": 0,
  "debug": false,
  "schedule": {
    "enabled": false,
    "start_time": "22:00"
  },
  "modbus": {
    "port": "/dev/ttyUSB0",
    "baudrate": 9600,
    "slave_id": 1,
    "backend": "auto"
  }
}
```

## Як запускати

### Ручний запуск

```bash
python main.py
```

### Запуск з перевизначенням параметрів

```bash
python main.py --mode LT --doors 2
python main.py --mode MT --doors 5 --debug
```

### Запуск через вже підготовлений Raspberry сценарій

```bash
./scripts/start_on_rpi.sh
```

### Якщо хочете примусово використовувати stable backend, який уже показав успішні read/write на Raspberry

```bash
MODBUS_BACKEND=minimalmodbus MODBUS_PORT=/dev/ttyUSB0 python main.py
```

## Логування

Основний runtime-лог тесту:

```bash
logs/test.log
```

Логується:
- старт/стоп тесту
- відкриття/закриття дверей
- стани реле
- помилки Modbus
- перепідключення

## Важливо

- Для фактичного ISO-тесту використовуйте `main.py`, а не старий demo/web flow.
- Web UI залишено для сервісного контролю, але основний алгоритм циклів тепер винесений в окрему архітектуру за ТЗ.
- Якщо `pymodbus` нестабільний у вашому середовищі, використовуйте `MODBUS_BACKEND=minimalmodbus`.
