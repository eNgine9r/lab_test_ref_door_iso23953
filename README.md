# Door Test Controller

Door Test Controller — модульна система для Raspberry Pi для ресурсних тестів дверей вітрин через Modbus RTU (RS‑485).

## Що вже готово

- Керування дверима (manual/automatic)
- Лічильник циклів по дверях
- Light relay control (auto OFF після 12 годин у `day` режимі)
- Watchdog + fail-safe
- Retry для Modbus команд
- Simulation mode без обладнання

## Швидкий запуск на Raspberry Pi (без локальної мережі)

> Мета цього етапу: **Raspberry має побачити USB/RS-485 адаптер і відповіді VRC модулю по Modbus RTU**.

### 1) Підключення

- Raspberry Pi ↔ USB-RS485 adapter
- RS-485 adapter ↔ VRC-C4/VRC-R8
- Встановіть параметри VRC:
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
python tools/rs485_probe.py --slave 1 --baudrate 9600
```

Якщо `"ok": true` — зв'язок з VRC підтверджено.

### 4) Запуск сервісу локально на Raspberry

```bash
cd /home/pi/door-test-system
./scripts/start_on_rpi.sh
```

За замовчуванням Flask підіймається на `127.0.0.1:5000` (без LAN).

## Systemd автозапуск

```bash
sudo cp door_test_controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now door_test_controller
sudo systemctl status door_test_controller
```

## Важливі ENV параметри

- `SIMULATION_MODE=0` — реальне обладнання
- `MODBUS_AUTODETECT=1` — авто-пошук серійного порту
- `MODBUS_PORT=/dev/ttyUSB0` — зафіксувати порт вручну
- `MODBUS_SLAVE_ID=1`
- `HOST=127.0.0.1`

## Debug чекліст, якщо VRC не відповідає

1. Перевірити A/B лінії RS-485 (інколи треба поміняти місцями).
2. Перевірити що `slave id` на модулі = `MODBUS_SLAVE_ID`.
3. Перевірити живлення модуля реле.
4. Спробувати явно задати порт:

```bash
MODBUS_PORT=/dev/ttyUSB0 python tools/rs485_probe.py --slave 1 --baudrate 9600
```

5. Перевірити логи:

```bash
tail -f logs/system.log
```
