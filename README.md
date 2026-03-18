# Door Test Controller

Door Test Controller — модульна система для Raspberry Pi для ресурсних тестів дверей вітрин через Modbus RTU (RS‑485).

## Актуальна апаратна ціль

Проєкт орієнтований **лише на VRC-R6** (6 реле, 6 входів).

## Аналіз вашого звіту тестування

З вашого звіту видно:

- Raspberry Pi **бачить адаптер коректно**: `CP2104 USB to UART Bridge Controller` і `ttyUSB0` присутній. Це означає, що драйвер і USB-рівень працюють.
- `pyserial` тест проходить: порт `/dev/ttyUSB0` відкривається без помилки. Це означає, що проблема **не в доступі до порту**.
- `minimalmodbus` успішно читає та пише в `VRC-R6`. Отже, **RS485 фізика та сам Modbus канал реально працюють**.
- Проблема була саме в реалізації через `pymodbus 3.12.1`: у вашому логові видно помилку `unexpected keyword argument 'slave'`. Це була реальна несумісність API `pymodbus 2.x / 3.x`, а не проблема кабелю чи модуля.

## Що виправлено

### 1. Сумісність з `pymodbus 2.x / 3.x / 3.12+`

Тепер код автоматично визначає, який ідентифікатор треба передавати в Modbus-виклики:
- `device_id=`
- `unit=`
- `slave=`

Тобто більше немає жорсткої прив’язки до одного API.

### 2. Автоматичний fallback на `minimalmodbus`

Оскільки ваш реальний тест показав, що `minimalmodbus` працює, я зробив так, щоб контролер міг працювати через два backend-и:
- `pymodbus`
- `minimalmodbus`

А в режимі `MODBUS_BACKEND=auto` він:
1. пробує `pymodbus`,
2. якщо той не працює коректно — автоматично переключається на `minimalmodbus`.

### 3. Виправлений `rs485_probe.py`

`tools/rs485_probe.py` тепер:
- підтримує новий API `pymodbus 3.12.1`,
- якщо `pymodbus` не зміг, пробує `minimalmodbus`,
- повертає не тільки `modbus_ok`, а й **через який backend** вдалося встановити зв’язок.

### 4. Веб-інтерфейс показує активний Modbus backend

У статусі тепер видно:
- Modbus port
- Modbus backend

Тобто ви одразу побачите, через що саме система реально працює на Raspberry.

## Що запускати зараз на Raspberry

### Рекомендований запуск

```bash
cd ~/lab_test_ref_door_iso23953
./scripts/start_on_rpi.sh
```

Стартовий скрипт тепер:
- ставить залежності,
- ставить `minimalmodbus`,
- фіксує `MODBUS_PORT=/dev/ttyUSB0`, якщо порт існує,
- запускає probe,
- запускає low-level serial test,
- стартує `app.py`.

### Якщо хочете примусово запуск через `minimalmodbus`

Оскільки саме він у вас вже підтверджено працює, для **найшвидшого стабільного запуску** рекомендую такий варіант:

```bash
cd ~/lab_test_ref_door_iso23953
MODBUS_BACKEND=minimalmodbus MODBUS_PORT=/dev/ttyUSB0 ./scripts/start_on_rpi.sh
```

Це обійде проблемний шар `pymodbus`, якщо він знову поводитиметься нестабільно саме у вашому середовищі.

## Діагностика, якщо ще буде проблема

### Перевірка системи

```bash
./tools/rs485_system_check.sh
```

### Перевірка порту

```bash
python tools/serial_port_test.py --port /dev/ttyUSB0
```

### Перевірка probe

```bash
python tools/rs485_probe.py --slave 1 --baudrate 9600 --port /dev/ttyUSB0
```

### Перевірка через minimalmodbus

```bash
python tools/minimalmodbus_test.py --port /dev/ttyUSB0 --slave 1
python tools/minimalmodbus_test.py --port /dev/ttyUSB0 --slave 1 --write
```

## Висновок по вашому звіту

По факту, у вас **залізо вже працює**. Проблема була не в Raspberry, не в `/dev/ttyUSB0`, не в CP2104 і не в RS485 лінії. Проблема була в програмній несумісності `pymodbus` API у проєкті. Після цих змін проєкт повинен уже запускатися значно стабільніше, а в разі проблем з `pymodbus` — автоматично або вручну переходити на `minimalmodbus`, який у вас уже успішно пройшов read/write тест.
