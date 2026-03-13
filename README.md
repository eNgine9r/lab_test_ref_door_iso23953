# Door Test Controller

Door Test Controller — модульна система для Raspberry Pi, яка керує стендом ресурсних тестів дверей холодильних вітрин через Modbus RTU (RS-485), має веб-панель на Flask, лічильники циклів, графік у реальному часі, watchdog, fail-safe, та simulation mode.

## Архітектура

Browser (PC) → Flask Web Server (Raspberry Pi) → Door Logic / Controller → Modbus RTU → RS-485 → VRC-C4/VRC-R8.

## Можливості

- Керування дверима (manual/automatic)
- Лічильник циклів по дверях
- Відображення циклів у вигляді live-даних (без графіка)
- Light relay control з авто-вимкненням після 12 годин day-тесту
- Вибір мови: Українська / English
- Автотема (light/dark) через prefers-color-scheme
- Watchdog timeout (10s)
- Fail-safe: всі реле OFF при помилках
- Retry Modbus команд (до 3 разів)
- Автовідновлення зв'язку кожні 5с
- Simulation mode без RS-485 обладнання
- Статичний demo для GitHub Pages (`demo/`)

## Структура

```text
door-test-system
├── app.py
├── config.py
├── door_logic.py
├── modbus_controller.py
├── hardware_simulator.py
├── cycle_counter.py
├── watchdog.py
├── templates/dashboard.html
├── static/style.css
├── static/dashboard.js
├── demo/index.html
├── data/cycles.json
├── logs/system.log
├── requirements.txt
└── README.md
```

## Запуск

```bash
pip install -r requirements.txt
python app.py
```

Відкрити: `http://127.0.0.1:5000` або на Raspberry `http://192.168.50.10`.

## Simulation Mode

```bash
SIMULATION_MODE=1 python app.py
```

У simulation mode всі реле/двері емулюються модулем `hardware_simulator.py`.

## Systemd автозапуск

Приклад юніта у `door_test_controller.service`.

```bash
sudo cp door_test_controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now door_test_controller
```

## GitHub Pages Demo

Вміст `demo/` можна публікувати через GitHub Pages.

## Screenshots

Додайте скриншоти:
- dashboard screenshot
- light relay status
