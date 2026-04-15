# Door Test Controller

Door Test Controller — Raspberry Pi система для ресурсних тестів дверей холодильних вітрин через VRC-R6 по RS-485 Modbus RTU.

## Основний сценарій для користувача

Проєкт тепер орієнтований на **максимально простий веб-запуск**:

1. Користувач запускає один скрипт:
   ```bash
   ./scripts/start_on_rpi.sh
   ```
2. Скрипт піднімає Flask веб-інтерфейс.
3. Скрипт автоматично намагається відкрити браузер на адресі:
   ```text
   http://127.0.0.1:5000/
   ```
4. У веб-інтерфейсі користувач обирає:
   - режим `MT` або `LT`
   - кількість дверей у випадаючому меню
   - тривалість тесту
   - за потреби `Debug`
   - за потреби дату і час відкладеного запуску
5. Далі достатньо натиснути кнопку **«Старт»**.

Саме цей сценарій слід показувати оператору як основний.

## Що робить веб-інтерфейс

Веб-інтерфейс тепер запускає саме **ISO 23953-2 test flow**, а не старий спрощений цикл.

Кнопка **Start** у браузері запускає:
- startup / load phase
- основний тестовий цикл `MT` або `LT`
- night mode наприкінці тесту
- аварійне/ручне зупинення через кнопку **Stop**

Також у UI залишено сервісні кнопки:
- ручне відкриття окремих дверей
- керування світлом
- скидання лічильників циклів
- таймер з countdown до запланованого старту
- scrollable лог циклів

## Логіка ISO 23953-2

### 1. Startup / імітація завантаження

- Двері відкриваються **почергово**: door 1 → 180 сек → закрити, потім door 2 → 180 сек → закрити і так далі
- Після завершення startup виконується стабілізаційна пауза 300 сек

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

`config.json` задає значення за замовчуванням, які веб-інтерфейс показує оператору під час старту.

## Як запускати

### Рекомендовано для оператора Raspberry Pi

```bash
./scripts/start_on_rpi.sh
```

### Якщо браузер не відкрився автоматично

Відкрийте вручну:

```text
http://127.0.0.1:5000/
```

### Альтернативний запуск тільки веб-сервера

```bash
python app.py
```

### Старий CLI-запуск ISO runner

CLI entrypoint `main.py` залишено в проєкті для сервісних або headless сценаріїв:

```bash
python main.py
python main.py --mode MT --doors 5 --debug
```

## Логування

Основні логи:

```bash
logs/system.log
logs/test.log
```

Логується:
- старт/стоп тесту
- відкриття/закриття дверей
- стани реле
- помилки Modbus
- перепідключення

## Важливо

- Для звичайного користувача основний сценарій — **веб-інтерфейс**.
- `scripts/start_on_rpi.sh` тепер запускає саме веб-сервер і намагається автоматично відкрити браузер.
- Якщо `pymodbus` нестабільний у вашому середовищі, використовуйте `MODBUS_BACKEND=minimalmodbus`.

## Relay Auto ON (Relay #6)

- Під час запуску `app.py` система автоматично вмикає relay #6 (Light) **до старту тестового циклу**.
- Є retry-логіка (`STARTUP_LIGHT_RETRIES`/`STARTUP_LIGHT_RETRY_DELAY_SEC`) на випадок, якщо Modbus ще не готовий.

## Offline mode (без інтернету)

### Підготувати bundle на онлайн-машині

```bash
./scripts/build_offline_bundle.sh
```

Це створює локальний пакет залежностей у:

```text
third_party/wheels/
```

### Встановити офлайн на Raspberry Pi

```bash
./scripts/install_offline.sh
```

Скрипт використовує portable virtual environment:

```text
.venv_portable/
```

## Auto start на boot + kiosk

Сервіс `door_test_controller.service` запускає:

- `scripts/kiosk_start.sh`
- веб-застосунок
- Chromium у kiosk mode на `http://127.0.0.1:5000/`

Приклад інсталяції сервісу:

```bash
sudo cp door_test_controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable door_test_controller.service
sudo systemctl start door_test_controller.service
```

## Вертикальна орієнтація екрана

`scripts/rotate_screen.sh` робить:

1. Спробу прописати rotation у `config.txt` (для boot-level rotation).
2. Якщо це недоступно — fallback через `xrandr` runtime rotation.

## Touch UX та локалізація

- Вимкнено глобальне випадкове виділення тексту, додано smooth scrolling.
- Додано перемикач мови (UA/EN) у веб-інтерфейсі.
- Мова за замовчуванням: **українська**.
- Вибір мови зберігається у `localStorage`.

## Час руху пневматики (відкриття/закриття)

Додано окремі параметри, щоб враховувати реальний рух циліндра:

```json
"door_open_time_sec": 0.5,
"door_close_time_sec": 0.5
```

### Принцип обчислення циклу

Для кожних дверей:

1. старт відкриття
2. очікування `door_open_time_sec`
3. двері повністю відкриті → стартує **чистий** LT/MT hold
4. очікування LT/MT hold
5. старт закриття
6. очікування `door_close_time_sec`
7. цикл завершено

Тобто фактичний час циклу дверей:

```text
total_cycle_time = hold_time(LT/MT) + door_open_time_sec + door_close_time_sec
```

> LT/MT лишається тільки часом у повністю відкритому стані, без часу руху.

### Логи переходу Day → Night

У логах фіксуються поля:

- `testStartTime`
- `calculatedNightModeTime`
- `actualNightModeTime`
- `currentMode`
- `reason`

Щоб можна було зіставити плановий і фактичний момент переходу.
