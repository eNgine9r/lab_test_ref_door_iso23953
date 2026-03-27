const i18n = {
  uk: {
    title: 'Door Test Controller',
    subtitle: 'Запустіть сервер і натисніть одну кнопку нижче, щоб почати автоматичний тест дверей.',
    language: 'Мова',
    event: 'Last event:',
    error: 'Error:',
    timer: 'Таймер:',
    quick_start: 'Швидкий запуск',
    quick_help: 'Оберіть режим тесту, кількість дверей і натисніть «Старт». Інші параметри вже підставляються автоматично.',
    mode: 'Режим тесту',
    door_count: 'Кількість дверей',
    duration: 'Тривалість тесту (год)',
    door_open_time: 'Час відкриття дверей (сек)',
    door_close_time: 'Час закриття дверей (сек)',
    debug: 'Debug режим (час у 10 разів швидше)',
    schedule_enable: 'Запланувати запуск',
    schedule_start: 'Дата і час старту',
    schedule_state: 'Schedule:',
    start: 'Старт',
    stop: 'Стоп',
    status: 'Статус системи',
    system_status: 'System status:',
    test: 'Test:',
    light: 'Light relay:',
    doors: 'Стан дверей',
    manual_controls: 'Ручне керування',
    manual_help: 'Сервісні кнопки для перевірки конкретних дверей або світла.',
    light_on: 'Світло УВІМК',
    light_off: 'Світло ВИМК',
    reset: 'Скинути цикли',
    cycles: 'Цикли',
  },
  en: {
    title: 'Door Test Controller',
    subtitle: 'Start the server and press one button below to begin the automatic door test.',
    language: 'Language',
    event: 'Last event:',
    error: 'Error:',
    timer: 'Timer:',
    quick_start: 'Quick start',
    quick_help: 'Choose the test mode and number of doors, then press Start. Other parameters are filled in automatically.',
    mode: 'Test mode',
    door_count: 'Door count',
    duration: 'Test duration (hours)',
    door_open_time: 'Door opening time (sec)',
    door_close_time: 'Door closing time (sec)',
    debug: 'Debug mode (10x faster timing)',
    schedule_enable: 'Schedule start',
    schedule_start: 'Scheduled date and time',
    schedule_state: 'Schedule:',
    start: 'Start',
    stop: 'Stop',
    status: 'System status',
    system_status: 'System status:',
    test: 'Test:',
    light: 'Light relay:',
    doors: 'Door states',
    manual_controls: 'Manual controls',
    manual_help: 'Service buttons for checking a specific door or the light relay.',
    light_on: 'Light ON',
    light_off: 'Light OFF',
    reset: 'Reset cycles',
    cycles: 'Cycles',
  },
};

const LANG_STORAGE_KEY = 'door_test_ui_lang';
let formInitialized = false;
let formDirty = false;
const formFields = ['mode', 'door_count', 'test_duration_hours', 'door_open_time_sec', 'door_close_time_sec', 'debug', 'schedule_enabled', 'scheduled_start'];

function applyLang(lang) {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.dataset.i18n;
    if (i18n[lang]?.[key]) {
      const textNode = Array.from(el.childNodes).find((node) => node.nodeType === Node.TEXT_NODE);
      if (textNode) {
        textNode.nodeValue = i18n[lang][key];
      } else {
        el.textContent = i18n[lang][key];
      }
    }
  });
}

function setLanguage(lang) {
  const selected = i18n[lang] ? lang : 'uk';
  localStorage.setItem(LANG_STORAGE_KEY, selected);
  document.documentElement.lang = selected;
  document.getElementById('langSelect').value = selected;
  applyLang(selected);
}

function initLanguage() {
  const stored = localStorage.getItem(LANG_STORAGE_KEY);
  const lang = stored && i18n[stored] ? stored : 'uk';
  setLanguage(lang);
}

function markFormDirty() {
  formDirty = true;
}

function attachFormDirtyHandlers() {
  formFields.forEach((id) => {
    const el = document.getElementById(id);
    el.addEventListener('input', markFormDirty);
    el.addEventListener('change', markFormDirty);
  });
}

function formatCountdown(seconds) {
  if (seconds === null || seconds === undefined) {
    return '-';
  }
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  const parts = [];
  if (days) parts.push(`${days}d`);
  parts.push(String(hours).padStart(2, '0'));
  parts.push(String(minutes).padStart(2, '0'));
  parts.push(String(secs).padStart(2, '0'));
  return parts.join(days ? ' ' : ':');
}

async function postJson(url, body = {}) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || payload.message || `Request failed: ${response.status}`);
  }
  return payload;
}

function updateDoorButtons(doorCount) {
  document.querySelectorAll('[data-door]').forEach((btn) => {
    btn.disabled = parseInt(btn.dataset.door, 10) > doorCount;
  });
}

function syncForm(status) {
  if (status.test_running || status.schedule_status === 'WAITING') {
    formDirty = false;
  }
  if (formInitialized && formDirty) {
    return;
  }
  document.getElementById('mode').value = status.selected_mode || 'MT';
  document.getElementById('door_count').value = String(status.selected_door_count || 4);
  document.getElementById('test_duration_hours').value = status.selected_test_duration_hours || 12;
  document.getElementById('debug').checked = Boolean(status.selected_debug);
  document.getElementById('door_open_time_sec').value = status.selected_door_open_time_sec ?? 0.5;
  document.getElementById('door_close_time_sec').value = status.selected_door_close_time_sec ?? 0.5;
  document.getElementById('schedule_enabled').checked = Boolean(status.schedule_enabled);
  document.getElementById('scheduled_start').value = status.scheduled_start || '';
  formInitialized = true;
}

async function startTest() {
  const payload = {
    mode: document.getElementById('mode').value,
    door_count: parseInt(document.getElementById('door_count').value, 10),
    test_duration_hours: parseInt(document.getElementById('test_duration_hours').value, 10),
    door_open_time_sec: parseFloat(document.getElementById('door_open_time_sec').value),
    door_close_time_sec: parseFloat(document.getElementById('door_close_time_sec').value),
    debug: document.getElementById('debug').checked,
    schedule_enabled: document.getElementById('schedule_enabled').checked,
    scheduled_start: document.getElementById('scheduled_start').value,
  };
  await postJson('/start', payload);
  formDirty = false;
  await refresh();
}

async function stopTest() {
  await postJson('/stop');
  formDirty = false;
  await refresh();
}

document.getElementById('start').onclick = () => startTest().catch(showError);
document.getElementById('stop').onclick = () => stopTest().catch(showError);
document.getElementById('reset').onclick = () => postJson('/reset').then(refresh).catch(showError);
document.getElementById('lightOn').onclick = () => postJson('/light', { on: true }).then(refresh).catch(showError);
document.getElementById('lightOff').onclick = () => postJson('/light', { on: false }).then(refresh).catch(showError);
document.getElementById('langSelect').addEventListener('change', (event) => setLanguage(event.target.value));
document.querySelectorAll('[data-door]').forEach((btn) => {
  btn.onclick = () => postJson(`/open/${btn.dataset.door}`).then(refresh).catch(showError);
});
attachFormDirtyHandlers();

function showError(error) {
  document.getElementById('error').textContent = error.message;
}

async function refresh() {
  const [status, cycles] = await Promise.all([
    fetch('/status').then((r) => r.json()),
    fetch('/cycles').then((r) => r.json()),
  ]);

  document.getElementById('status').textContent = status.system_status;
  document.getElementById('statusPill').textContent = status.system_status;
  document.getElementById('running').textContent = status.test_running ? 'running' : 'stopped';
  document.getElementById('event').textContent = status.last_event;
  document.getElementById('error').textContent = status.error_message || '-';
  document.getElementById('lightStatus').textContent = status.light_relay_on ? 'ON' : 'OFF';
  document.getElementById('modbusPort').textContent = status.modbus_port || '-';
  document.getElementById('modbusBackend').textContent = status.modbus_backend || '-';
  document.getElementById('activeMode').textContent = status.test_mode || '-';
  document.getElementById('activeDoorCount').textContent = status.door_count || '-';
  document.getElementById('activeDuration').textContent = status.test_duration_hours || '-';
  document.getElementById('activeDebug').textContent = status.debug ? 'ON' : 'OFF';
  document.getElementById('activeDoorOpenTime').textContent = status.door_open_time_sec ?? '-';
  document.getElementById('activeDoorCloseTime').textContent = status.door_close_time_sec ?? '-';
  document.getElementById('scheduleState').textContent = status.schedule_status || 'IDLE';
  document.getElementById('scheduleCountdown').textContent = status.schedule_status === 'WAITING'
    ? `${status.scheduled_start || ''} (${formatCountdown(status.seconds_until_start)})`
    : '-';

  syncForm(status);

  const doorsEl = document.getElementById('doors');
  doorsEl.innerHTML = '';
  Object.entries(status.doors).slice(0, status.selected_door_count || 5).forEach(([name, doorState]) => {
    const div = document.createElement('div');
    div.className = `door ${doorState}`;
    div.textContent = `${name} ● ${doorState}`;
    doorsEl.appendChild(div);
  });

  updateDoorButtons(status.selected_door_count || 5);
  document.getElementById('cyclesData').textContent = JSON.stringify({
    cycles: cycles.cycles,
    recent_events: cycles.events || [],
  }, null, 2);
}

initLanguage();
refresh().catch(showError);
setInterval(() => refresh().catch(showError), 1000);
