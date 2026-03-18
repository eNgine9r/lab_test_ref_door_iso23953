# Door Test Controller

Door Test Controller — модульна система для Raspberry Pi для ресурсних тестів дверей вітрин через Modbus RTU (RS‑485).

## Актуальна апаратна ціль

Проєкт тепер орієнтований **лише на VRC-R6** (6 реле, 6 входів). VRC-C4/VRC-R8 більше не використовуємо.

## Що вже готово

- Керування дверима (manual/automatic)
- Лічильник циклів по дверях
- Журнал подій циклів з timestamp для `door open/close`
- Light relay control (auto OFF після 12 годин у `day` режимі)
- Watchdog + fail-safe
- Retry для Modbus команд
- Simulation mode без обладнання

## Швидкий запуск на Raspberry Pi (без локальної мережі)

> Мета: **Raspberry має побачити USB/RS-485 адаптер і відповіді VRC-R6 по Modbus RTU**.

### 1) Підключення

- Raspberry Pi ↔ USB-RS485 adapter
- RS-485 adapter ↔ VRC-R6
- Параметри Modbus:
  - baudrate `9600`
  - parity `N`
  - stopbits `1`
  - bytesize `8`
  - slave id `1`

### 2) Перевірити що Raspberry бачить RS-485 порт

```bash
ls /dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA* /dev/ttyS* 2>/dev/null
```

### 3) Запустити Modbus probe

```bash
cd /home/pi/door-test-system
python tools/rs485_probe.py --slave 0 --baudrate 9600 --retries 3
```

Якщо `"ok": true` — зв'язок з VRC-R6 підтверджено.

### 4) Запуск сервісу локально на Raspberry

```bash
cd /home/pi/door-test-system
./scripts/start_on_rpi.sh
```

За замовчуванням Flask підіймається на `127.0.0.1:5000` (без LAN).

## API

- `GET /cycles` повертає:
  - `cycles`: лічильники циклів
  - `events`: журнал подій `open/close` з часом та дверима

## Debug чекліст, якщо VRC-R6 не відповідає

1. Перевірити A/B лінії RS-485 (інколи треба поміняти місцями).
2. Перевірити `slave id` на модулі.
3. Перевірити живлення VRC-R6.
4. Явно задати порт:

```bash
MODBUS_PORT=/dev/ttyUSB0 python tools/rs485_probe.py --slave 0 --baudrate 9600 --retries 3
```

5. Перевірити логи:

```bash
tail -f logs/system.log
```


> Примітка: якщо модуль повертає Modbus exception code, це все одно вважається валідною відповіддю для перевірки лінку RS-485.
