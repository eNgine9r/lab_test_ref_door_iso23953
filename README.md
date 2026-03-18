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

## Діагностика та виправлення RS485 на Raspberry Pi

### 1. Перевірка системи

```bash
./tools/rs485_system_check.sh
```

Скрипт виконує:
- `lsusb`
- `dmesg | grep -i usb`
- `dmesg | grep tty`
- перевірку `/dev/ttyUSB0`
- список serial-портів.

### 2. Драйвери USB-RS485

Визначити чіп адаптера через:

```bash
lsusb
```

Якщо треба, встановити драйвери:

```bash
sudo apt update
sudo apt install -y usb-modeswitch
sudo modprobe usbserial
sudo modprobe ftdi_sio
sudo modprobe ch341
sudo modprobe cp210x
```

### 3. Доступ до порту

```bash
sudo usermod -aG dialout pi
sudo reboot
```

### 4. Низькорівневий тест порту (pyserial)

```bash
python tools/serial_port_test.py --port /dev/ttyUSB0
```

Це перевіряє, що порт відкривається без помилки.

### 5. Modbus probe через pymodbus

```bash
python tools/rs485_probe.py --slave 1 --baudrate 9600 --port /dev/ttyUSB0
```

Або скан slave id 1..10:

```bash
python tools/rs485_probe.py --slave 0 --baudrate 9600 --port /dev/ttyUSB0 --retries 3
```

#### Що виправлено

- probe більше не дає хибний `modbus_ok: false`, якщо пристрій відповів `Modbus exception code`
- probe пробує кілька функцій читання
- probe підтримує різницю між `pymodbus 2.x` і `3.x` (`unit=` vs `slave=`)
- виводиться `pymodbus_version` для діагностики.

### 6. MinimalModbus тест

```bash
python tools/minimalmodbus_test.py --port /dev/ttyUSB0 --slave 1
python tools/minimalmodbus_test.py --port /dev/ttyUSB0 --slave 1 --write
```

Окремий тест корисний для перевірки читання/запису незалежно від `pymodbus`.

### 7. Сумісність pymodbus 2.x / 3.x

У проєкті виправлено несумісність API:
- код більше не покладається жорстко лише на `slave=`
- аргумент пристрою визначається автоматично через сигнатуру метода, тому однаково працює і з `unit=`, і зі `slave=`.

### 8. Запуск локально на Raspberry

```bash
cd /home/pi/door-test-system
./scripts/start_on_rpi.sh
```

Скрипт:
- створює venv
- ставить runtime-залежності
- ставить `minimalmodbus`
- запускає `rs485_probe.py`
- запускає `serial_port_test.py`
- стартує Flask локально.

### 9. Фізична перевірка RS485

Перевірити:
- A → A
- B → B
- GND підключено
- baudrate = 9600
- slave id = 1
- автонапрямок адаптера
- за потреби спробувати FTDI-адаптер.

### 10. Якщо порт є, але відповіді нема

Послідовність:

```bash
./tools/rs485_system_check.sh
python tools/serial_port_test.py --port /dev/ttyUSB0
python tools/rs485_probe.py --slave 0 --baudrate 9600 --port /dev/ttyUSB0 --retries 3
python tools/minimalmodbus_test.py --port /dev/ttyUSB0 --slave 1
```

### 11. Логи

```bash
tail -f logs/system.log
```

## Важливо

- Не змішувати API `pymodbus 2.x` і `3.x` вручну — у проєкті це вже враховано автоматично.
- Якщо адаптер відключити, `/dev/ttyUSB0` має зникати з системи — це окремий важливий тест Linux/USB.
