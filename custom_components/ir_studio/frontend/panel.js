/* IR Studio panel: no external CDN, passwords, keys or cloud requests. */
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const h = (v) => esc(v);
// The icon catalog is supplied and validated by the integration.
const ICON_BY_ID = new Map();
const setIconCatalog = items => {
  if (!Array.isArray(items)) return;
  ICON_BY_ID.clear();
  for (const icon of items)
    if (typeof icon?.id === 'string' && /^[a-z][a-z0-9_]*$/.test(icon.id) &&
        typeof icon?.mdi === 'string' && /^[a-z][a-z0-9-]*$/.test(icon.mdi))
      ICON_BY_ID.set(icon.id, icon);
};
const deviceIcon = id =>
  '<ha-icon class="device-icon" icon="mdi:' +
  h(ICON_BY_ID.get(id)?.mdi || 'remote') + '" aria-hidden="true"></ha-icon>';
const modalHeading = (icon, eyebrow, title, description) =>
  `<div class="modal-heading"><span class="modal-heading-icon" aria-hidden="true">${icon}</span><div class="modal-heading-copy"><span class="modal-eyebrow">${h(eyebrow)}</span><h3>${h(title)}</h3><p>${h(description)}</p></div></div>`;
// Visual inference changes *only the decorative icon*, never commands or device identity.
const visualTypeForName = (value) => {
  const name = String(value || '').toLowerCase();
  if (/projector|проектор/.test(name)) return 'projector';
  if (/smart.?tv|смарт.?тв/.test(name)) return 'tv_smart';
  if (/телевиз|(^|[^a-z])tv([^a-z]|$)/.test(name)) return 'tv_standard';
  if (/люстра|chandelier/.test(name)) return 'lamp';
  if (/настольн.*ламп|напольн.*ламп|торшер|лампа|(^|[^a-z])lamp([^a-z]|$)/.test(name)) return 'lamp';
  if (/светильник|light fixture/.test(name)) return 'white_dimmer';
  if (/rgb|led.?strip|led.?controller|лента|подсвет/.test(name)) return 'rgb_controller';
  if (/av.?receiver|ресивер|домашн.*кинотеатр/.test(name)) return 'av_receiver';
  if (/dvr|vcr|видеорекордер|видеомагнитофон/.test(name)) return 'dvr_vcr';
  if (/portable.?ac|мобильн.*кондиционер|оконн.*кондиционер/.test(name)) return 'portable_ac';
  if (/ceiling.?fan|потолочн.*вентилятор/.test(name)) return 'ceiling_fan';
  if (/кондицион|air conditioner/.test(name)) return 'split_ac';
  if (/приставк|set.top/.test(name)) return 'stb_general';
  if (/медиаплеер|media player|streaming player/.test(name)) return 'streaming_player';
  if (/dvd|blu.?ray|проигрывател/.test(name)) return 'dvd_bluray';
  if (/саундбар|soundbar/.test(name)) return 'soundbar';
  if (/вентилятор|fan/.test(name)) return 'floor_tower_fan';
  return 'blank_remote';
};
const profileTemplateId = (profile) => profile?.profile_type ||
  profile?.template_id || visualTypeForName(profile?.name);
const profileGlyph = (profile) => profile?.icon_mdi?.startsWith("mdi:") ?
  '<ha-icon class="device-icon" icon="' + h(profile.icon_mdi) + '" aria-hidden="true"></ha-icon>' :
  deviceIcon(profile?.icon || profileTemplateId(profile));


// A restored backup's "needs_check" does not mean its old commands vanished.
// Foreign Remote CodeStores are intentionally opaque, so distinguish known
// IR Studio payloads from historically learned commands pending verification.
const profileLearningSummary = (buttons = []) => {
  let learned = 0, needsCheck = 0;
  for (const button of buttons) {
    if (button.verified === true ||
        button.code_in_local_store === true ||
        button.code_in_tuya_ir_store === true ||
        ['stored', 'verified'].includes(button.status)) {
      learned++;
    } else if (button.status === 'needs_check') {
      needsCheck++;
    }
  }
  return {total: buttons.length, learned, needsCheck, accounted: learned + needsCheck};
};

const EN_TEXT = [
  ["Иконка пульта", "Remote icon"],
  ["Выбрать иконку", "Choose icon"],
  ["Поиск иконки…", "Search icons…"],
  ["Без изменения ИК-команд", "Does not change IR commands"],
  ["Выбери иконку и локальный ИК-шлюз.", "Choose an icon and a local IR hub."],
  ["Измени название, иконку или локальный исполнитель.", "Change the name, icon or local executor."],
  ["Иконка меняет только внешний вид. Кнопки и ИК-сигналы не меняются.", "The icon changes appearance only. Commands and learned IR signals stay untouched."],
  ["Выбор иконки не создаёт кнопки или ИК-коды.", "Choosing an icon does not generate buttons or IR codes."],
  ["Изменение иконки не затрагивает обученные команды.", "Choosing a new icon does not change learned commands."],
  ["Дополнительно: загрузка файла ИК-сигналов", "Optional: import an IR signal file"],
  ["Основной способ — обучить команды оригинальным пультом. Импорт совместимого файла .ir необязателен.", "The normal method is to learn commands from the original remote. Importing a compatible .ir file is optional."],
  ["Физический ИК-шлюз для обучения и отправки сигналов.", "Physical IR hub for learning and sending commands."],
  ["После создания выбери английские команды из библиотеки и обучи их оригинальным пультом.", "After creation, choose English commands from the library and learn them with the original remote."],
  ["Удалить пульт", "Delete remote"],
  ["Новый пульт", "New remote"],
  ["Коды прежнего драйвера не переносятся.", "Codes from the previous driver are not transferred."],
  ["Добавь локальную HA remote-сущность через Настройки → Устройства и службы.", "Add a local HA remote entity in Settings → Devices & services."],
  ["НОВЫЙ ПРОФИЛЬ", "NEW PROFILE"],
  ["НАСТРОЙКИ ПРОФИЛЯ", "PROFILE SETTINGS"],
  ["Физический ИК-шлюз, который будет обучать и отправлять сигналы.", "The physical IR hub used to learn and send signals."],
  ["Нет локального ИК-шлюза", "No local IR hub"],
  ["Команды и ИК-сигналы", "Commands and IR signals"],
  ["Сохранность ИК-кодов", "IR code safety"],
  ["Локальный исполнитель", "Local executor"],
  ["Название пульта", "Remote name"],
  ["Сначала добавь локальную HA remote-сущность в Настройки → Устройства и службы.", "First add a local HA remote entity in Settings → Devices & services."],
  ["При смене исполнителя коды из прежнего драйвера не переносятся.", "Codes are not moved when the executor changes."],
  ["Доступный ИК-шлюз выбран автоматически. При необходимости выбери другой.", "An available IR hub was selected automatically. You can choose another."],
  ["Выбери доступный локальный ИК-шлюз.", "Choose an available local IR hub."],
  [
    "Поиск шаблона",
    "Search templates"
  ],
  [
    "Название, тип или модель…",
    "Name, type, or model…"
  ],
  [
    "Категория",
    "Category"
  ],
  [
    "Все категории",
    "All categories"
  ],
  [
    "Подключение ИК-шлюза",
    "IR hub setup"
  ],
  [
    "Исполнитель — локальная remote-сущность",
    "Executor — local remote entity"
  ],
  [
    "Выбирай локальную сущность Tuya Local или другого LAN-драйвера. Облачные Remote не подходят для автономного управления.",
    "Choose a local Tuya Local or other LAN driver entity. Cloud remotes are not suitable for autonomous control."
  ],

  [
    "Tuya Local использует собственное окно обучения — до 30 секунд.",
    "Tuya Local uses its own learning window of up to 30 seconds."
  ],
  [
    "Tuya Local хранит DP202-коды в собственном хранилище. Обучай и отправляй команды через IR Studio; для сохранения кодов включай полную резервную копию Home Assistant.",
    "Tuya Local stores DP202 codes in its own storage. Learn and send through IR Studio; use a full Home Assistant backup to preserve those codes."
  ],
  [
    "Сохранено в Tuya Local",
    "Saved by Tuya Local"
  ],
  [
    "Нет WebSocket-сессии Home Assistant",
    "Home Assistant WebSocket session is unavailable"
  ],
  [
    "Не удалось получить настройки: ",
    "Could not load settings: "
  ],
  [
    "Нет локальных remote-сущностей — сначала добавь ИК-драйвер в Home Assistant",
    "No local remote entities — add an IR driver in Home Assistant"
  ],
  [
    "не найдена",
    "not found"
  ],
  [
    "сохранено",
    "saved"
  ],
  [
    "названий кнопок",
    "button names"
  ],
  [
    "ИК Студия",
    "IR Studio"
  ],
  [
    "Локальные ИК-пульты · Home Assistant",
    "Local IR remotes · Home Assistant"
  ],
  [
    "Обновить",
    "Refresh"
  ],
  [
    "Резервная копия",
    "Backup"
  ],
  [
    "IR Studio управляет профилями и командами. Подключение физического хаба, обучение и отправка сигналов выполняются выбранной локальной HA remote-сущностью.",
    "IR Studio manages remote profiles and commands. The selected local Home Assistant remote entity handles hub connectivity, IR learning, and transmission."
  ],
  [
    "Пульты",
    "Remotes"
  ],
  [
    "Пока нет профилей",
    "No remotes yet"
  ],
  [
    "Добавить пульт",
    "Add remote"
  ],
  [
    "Подключение ИК-шлюза",
    "IR hub setup"
  ],
  [
    "Добавь устройство в Tuya Local через Smart Life/QR или ручные параметры, затем выбери созданную сущность remote.*.",
    "Add the device in Tuya Local using Smart Life/QR or manual credentials, then select the resulting remote.* entity."
  ],
  [
    "Выбери локальную remote-сущность Tuya Local или другого ИК-драйвера. Обучение и отправка выполняются самим драйвером.",
    "Select the local remote entity provided by Tuya Local or another IR driver. The driver performs learning and transmission."
  ],
  [
    "Переименовать",
    "Rename"
  ],
  [
    "Удалить профиль",
    "Delete remote"
  ],
  [
    "Исполнитель команд — HA remote-сущность",
    "Command executor — Home Assistant remote entity"
  ],
  [
    "Привязать",
    "Bind"
  ],
  [
    "Изменение исполнителя не переносит физические ИК-коды из старого хранилища.",
    "Changing the executor does not move IR codes from the previous driver's code store."
  ],
  [
    "Команды",
    "Commands"
  ],
  [
    "Обучай по одной кнопке. Перед запуском подготовь оригинальный пульт.",
    "Learn one button at a time. Keep the original remote ready."
  ],
  [
    "Поиск кнопки…",
    "Search commands…"
  ],
  [
    "Название, например Volume+",
    "Command name, e.g. Volume+"
  ],
  [
    "+ Добавить",
    "+ Add"
  ],
  [
    "Добавить набор",
    "Add command set"
  ],
  [
    "Выбери пульт или добавь новый",
    "Select a remote or create one"
  ],
  [
    "Для начала понадобится работающая HA remote-сущность физического IR-хаба.",
    "Start by connecting a Tuya IR hub or selecting an existing Home Assistant remote entity."
  ],
  [
    "Добавить первый пульт",
    "Add your first remote"
  ],
  [
    "Физически проверено",
    "Physically verified"
  ],
  [
    "Код сохранён",
    "Code saved"
  ],
  [
    "Требуется проверка",
    "Needs verification"
  ],
  [
    "Сохранение заявлено",
    "Save reported"
  ],
  [
    "Не обучена",
    "Not learned"
  ],
  [
    "Перетащить",
    "Drag"
  ],
  [
    "для изменения порядка",
    "to reorder"
  ],
  [
    "Переименовать пульт",
    "Rename remote"
  ],
  [
    "Новое название",
    "New name"
  ],
  [
    "Существующие ИК-коды сохранят прежний внутренний ключ и останутся доступными.",
    "Existing IR codes keep their internal key and remain available."
  ],
  [
    "Отмена",
    "Cancel"
  ],
  [
    "Сохранить",
    "Save"
  ],
  [
    "Переименовать кнопку",
    "Rename command"
  ],
  [
    "Внутреннее имя команды Remote не меняется — ранее обученный код не потеряется.",
    "The underlying Remote command key stays unchanged, so learned codes remain available."
  ],
  [
    "Шаблон",
    "Device template"
  ],
  [
    "Название пульта",
    "Remote name"
  ],
  [
    "HA remote — физический ИК-хаб",
    "Home Assistant remote — physical IR hub"
  ],
  [
    "В списке может быть и облачный Remote — выбирай только локальный.",
    "The list may include cloud remotes. Choose a local IR hub only."
  ],
  [
    "Добавить",
    "Create"
  ],
  [
    "Обучение:",
    "Learning:"
  ],
  [
    "Поднеси оригинальный пульт к ИК-приёмнику подключённого хаба.",
    "Point the original remote at the IR receiver on the connected hub."
  ],
  [
    "Нажми «Начать приём».",
    "Select Start learning."
  ],
  [
    "После запуска один раз нажми",
    "After learning starts, press once"
  ],
  [
    "на оригинальном пульте.",
    "on the original remote."
  ],
  [
    "Держи пульт рядом, пока не появится результат.",
    "Keep the remote close until the result appears."
  ],
  [
    "Окно ожидания сигнала",
    "Signal timeout"
  ],
  [
    "30 секунд",
    "30 seconds"
  ],
  [
    "45 секунд",
    "45 seconds"
  ],
  [
    "60 секунд",
    "60 seconds"
  ],
  [
    "Если Remote unavailable, сначала восстанови соединение с YRC11. HTTP 400 означает ошибку, а не успешное обучение.",
    "If the remote is unavailable, restore the hub connection first. HTTP 400 is an error, not a successful learning result."
  ],
  [
    "Начать приём",
    "Start learning"
  ],
  [
    "Импорт raw-кода:",
    "Import IR code:"
  ],
  [
    "Импорт ИК-кода:",
    "Import IR code:"
  ],
  [
    "Импортировать код",
    "Import code"
  ],
  [
    "Удалить кнопку и её код из хранилища IR Studio",
    "Delete the command and its IR Studio payload"
  ],
  [
    "Импорт сохраняет код локально, но не подтверждает физическую работу устройства.",
    "Import stores the payload locally but does not verify physical operation."
  ],
  [
    "Формат сигнала",
    "Payload format"
  ],
  [
    "Tuya DP202 — исходная строка",
    "Tuya DP202 — original payload"
  ],
  [
    "RAW Base64 — u16LE",
    "RAW Base64 — u16LE"
  ],
  [
    "Вставь исходную строку DP202 из совместимого бэкапа. Не перекодируй её в Base64.",
    "Paste the original DP202 string from a compatible backup. Do not Base64-encode it."
  ],
  [
    "Вставь Base64 с RAW u16LE длительностями ИК-сигнала.",
    "Paste Base64 containing RAW u16LE IR timings."
  ],
  [
    "Сохранить код",
    "Save code"
  ],
  [
    "Операция не выполнена. Проверь журнал Home Assistant.",
    "Operation failed. Check the Home Assistant log."
  ],
  [
    "Этот Remote не поддерживает прямую отправку импортированного кода. Для него используй публичное remote.learn_command.",
    "This remote cannot send IR Studio imported codes directly. Use the public remote.learn_command service."
  ],
  [
    "Только raw Base64 из DP202 (u16 little-endian, микросекунды). Не вставляй Cloud Key ID, /rules blob или Local Key.",
    "Paste only a supported IR payload. Never paste a Cloud Key ID, /rules blob or Local Key."
  ],
  [
    "Base64 ИК-посылки",
    "IR payload"
  ],
  [
    "RAW-код сохраняется только в IR Studio. Внешний Remote необходимо обучать через remote.learn_command; импорт не изменяет его хранилище.",
    "RAW is stored only in IR Studio. Learn foreign remotes through remote.learn_command; importing does not alter their private code stores."
  ],
  [
    "Сохранить raw-код",
    "Save IR code"
  ],
  [
    "Запуск приёма…",
    "Starting learning…"
  ],
  [
    "Отправка команды…",
    "Sending command…"
  ],
  [
    "Операция отправлена в Home Assistant.",
    "The operation was sent to Home Assistant."
  ],
  [
    "Закрыть окно",
    "Close"
  ],
  [
    "Ошибка запуска: ",
    "Could not start: "
  ],
  [
    "Ожидаем ИК-сигнал",
    "Waiting for IR signal"
  ],
  [
    "Передаём ИК-команду",
    "Sending IR command"
  ],
  [
    "СЕЙЧАС нажми нужную кнопку оригинального пульта, направив его на приёмник YRC11.",
    "Press the matching button on the original remote and point it at the YRC11 receiver now."
  ],
  [
    "Обращаемся к локальному Remote…",
    "Contacting the local remote…"
  ],
  [
    "Закрыть окно (операция продолжится)",
    "Close window (operation continues)"
  ],
  [
    "Команда отправлена в драйвер (физическая реакция не проверялась)",
    "Command sent to the driver (physical response not verified)"
  ],
  [
    "Ошибка: ",
    "Error: "
  ],
  [
    "Ошибка проверки операции: ",
    "Could not check operation: "
  ],
  [
    "Сообщение",
    "Message"
  ],
  [
    "Закрыть",
    "Close"
  ],
  [
    "Ошибка: ",
    "Error: "
  ],
  [
    "Резервная копия пультов",
    "Remote backup"
  ],
  [
    "Выбери нужные пульты. Импорт не удаляет остальные пульты и не меняет их без выбранного режима замены.",
    "Select the remotes to include. Import leaves other remotes untouched unless you choose Replace."
  ],
  [
    "Экспорт",
    "Export"
  ],
  [
    "Импорт",
    "Import"
  ],
  [
    "Нет пультов",
    "No remotes"
  ],
  [
    "Выбрать все",
    "Select all"
  ],
  [
    "Снять выбор",
    "Clear selection"
  ],
  [
    "команд",
    "commands"
  ],
  [
    "Сырые ИК-сигналы включаются, только если они доступны в локальном хранилище IR Studio или поддерживаемого драйвера. Секретные ключи не экспортируются.",
    "IR payloads are included only when available in IR Studio or a supported local driver. Credentials and secret keys are never exported."
  ],
  [
    "Скачать выбранные пульты",
    "Download selected remotes"
  ],
  [
    "Файл резервной копии JSON",
    "JSON backup file"
  ],
  [
    "Сначала выбери JSON-файл.",
    "Choose a JSON file first."
  ],
  [
    "Если пульт уже существует",
    "If a remote already exists"
  ],
  [
    "Пропустить существующие (безопасно)",
    "Skip existing (safe)"
  ],
  [
    "Добавить отсутствующие кнопки",
    "Merge missing commands"
  ],
  [
    "Заменить выбранные пульты",
    "Replace selected remotes"
  ],
  [
    "Импортированные сигналы сохраняются в отдельном хранилище. Коды Tuya DP202 можно отправлять через нативный хаб ИК Студии после его привязки; преобразование в форматы сторонних драйверов не выполняется.",
    "Imported payloads are stored separately. Tuya DP202 codes can be sent through a bound native IR Studio hub; payloads are not converted to third-party driver formats."
  ],
  [
    "Импортировать выбранные пульты",
    "Import selected remotes"
  ],
  [
    "Файл слишком большой (максимум 5 МБ)",
    "File is too large (5 MB maximum)"
  ],
  [
    "Формат файла не поддерживается",
    "Unsupported file format"
  ],
  [
    "Не удалось прочитать JSON: ",
    "Could not read JSON: "
  ],
  [
    "Выбери хотя бы один пульт",
    "Select at least one remote"
  ],
  [
    "Ошибка экспорта: ",
    "Export failed: "
  ],
  [
    "Выбери файл и хотя бы один пульт",
    "Choose a file and at least one remote"
  ],
  [
    "Заменить ",
    "Replace "
  ],
  [
    " пульт(ов)? Старые профили будут заменены, но исходные RAW-коды внешнего драйвера не удаляются.",
    " remote(s)? Existing profiles will be replaced, but codes in the original external driver will not be deleted."
  ],
  [
    "Импорт: новых ",
    "Import: added "
  ],
  [
    ", объединено ",
    ", merged "
  ],
  [
    ", заменено ",
    ", replaced "
  ],
  [
    ", пропущено ",
    ", skipped "
  ],
  [
    "Ошибка импорта: ",
    "Import failed: "
  ],
  [
    "Удалить пульт «",
    "Delete remote “"
  ],
  [
    "» из ИК Студии? Коды в исходной Remote-интеграции останутся.",
    "” from IR Studio? Codes in the original Remote integration will remain."
  ],
  [
    "Удалить кнопку «",
    "Delete command “"
  ],
  [
    "» из ИК Студии?",
    "” from IR Studio?"
  ],
  [
    "Код сохранён. Нажми «Послать», чтобы проверить его физически.",
    "Code saved. Select Send to test it physically."
  ],
  [
    "Физическая реакция отмечена как проверенная.",
    "Physical response marked as verified."
  ],
  [
    "Сущность не найдена в Home Assistant",
    "Entity not found in Home Assistant"
  ],
  [
    "Максимум 24 профиля",
    "Maximum 24 remotes"
  ],
  [
    "Профиль с таким названием уже есть",
    "A remote with this name already exists"
  ],
  [
    "Пульт с таким названием уже существует",
    "A remote with this name already exists"
  ],
  [
    "Сущность не найдена",
    "Entity not found"
  ],
  [
    "Дождись завершения текущей операции перед удалением профиля",
    "Wait for the current operation to finish before deleting this remote"
  ],
  [
    "Максимум 200 команд на профиль",
    "Maximum 200 commands per remote"
  ],
  [
    "Команда уже существует",
    "Command already exists"
  ],
  [
    "Кнопка с таким названием уже существует",
    "A command with this name already exists"
  ],
  [
    "Команда не найдена",
    "Command not found"
  ],
  [
    "Нативный Remote ИК Студии сохранил код. Проверь отправку физически.",
    "The native IR Studio remote saved the code. Verify the physical transmission."
  ],
  [
    "HA завершил обучение без ошибки, но наличие raw-кода в хранилище не подтверждено. Попробуй отправку или проверь журнал интеграции.",
    "Home Assistant completed learning, but the raw code was not confirmed in storage. Try sending it or check the integration log."
  ],
  [
    "Вызов отправки завершился без ошибки. Подтверди, отреагировало ли устройство физически.",
    "The send call completed without an error. Confirm whether the device responded physically."
  ],
  [
    "Операция отменена",
    "Operation cancelled"
  ],
  [
    "Remote-сущность больше не существует",
    "The remote entity no longer exists"
  ],
  [
    "Remote сейчас unavailable. Сначала восстанови LAN-подключение к ИК-хабу",
    "The remote is unavailable. Restore the LAN connection to the IR hub first."
  ],
  [
    "Пока нет подтверждения сохранённого ИК-кода. Сначала обучи кнопку",
    "No saved IR code is confirmed yet. Learn this command first."
  ],
  [
    "Нужна успешно завершённая отправка",
    "A successfully completed send operation is required"
  ],
  [
    "Импорт поддерживается только для локальной интеграции tuya_ir",
    "Import is supported only for a local tuya_ir or native IR Studio remote"
  ],
  [
    "IR Studio не имеет доступа к хранилищу другого Remote",
    "Local IR code storage was not found"
  ],
  [
    "Выбери пульты для экспорта",
    "Select remotes to export"
  ],
  [
    "Профили хранят названия пультов и команд. ИК-коды сохраняются локально в IR Studio или в выбранном драйвере. Нативный транспорт Tuya IR Hub работает по LAN; для настройки нужен действующий Local Key.",
    "Profiles store remote and command names. IR codes are stored locally by IR Studio or the selected driver. The experimental native Tuya IR transport communicates over LAN and requires a valid Local Key."
  ],
  [
    "ИК-шлюз",
    "IR hub"
  ],
  [
    "Подключи Tuya IR Hub через кнопку «Добавить ИК-шлюз». Укажи IP, Device ID, Local Key и версию протокола. Нативный транспорт пока экспериментальный.",
    "Connect a Tuya IR Hub using Add IR hub. Enter its IP address, Device ID, Local Key and protocol version. Native transport is experimental."
  ],
  [
    "Не запускай одновременно два локальных TCP-драйвера на одном хабе: они могут мешать друг другу.",
    "Do not run two local TCP drivers against the same hub at the same time; they may interfere with each other."
  ],
  [
    "Выбери тип устройства — IR Studio создаст заготовку команд. Название пульта придумай сам. Тип шаблона не сохраняется и не влияет на дальнейшую работу.",
    "Choose a device type and IR Studio will create a starter command layout. Give the remote any name you like. The template type is not saved and has no effect on later operation."
  ],
  [
    "Каталог шаблонов не получен. Перезапусти Home Assistant после обновления IR Studio.",
    "The device-template catalog was not received. Restart Home Assistant after updating IR Studio."
  ],
  [
    "Подключи через Tuya / Smart Life по QR или введи локальные параметры вручную. После настройки IR Studio работает с хабом по LAN. Нативный транспорт пока экспериментальный.",
    "Connect through Tuya / Smart Life QR login or enter local credentials manually. After setup, IR Studio communicates with the hub over your LAN. The native transport is experimental."
  ],
  [
    "Шаблон устройства",
    "Device template"
  ],
  [
    "Пустой пульт",
    "Blank remote"
  ],
  [
    "Выбери шаблон…",
    "Choose a template…"
  ],
  [
    "Пустой профиль: команды можно добавить вручную или из библиотеки.",
    "Blank profile: add commands manually or from the library."
  ],
  [
    "команд",
    "commands"
  ],
  [
    "Название пульта",
    "Remote name"
  ],
  [
    "Например, Гостиная",
    "e.g. Living room"
  ],
  [
    "HA remote — физический ИК-хаб",
    "Home Assistant remote — physical IR hub"
  ],
  [
    "Выбирай локальный IR Studio Remote. Не используй облачный Remote для автономного управления.",
    "Choose the local IR Studio remote. Do not use a cloud remote for autonomous control."
  ],
  [
    "Добавить пульт",
    "Create remote"
  ],
  [
    "Библиотека команд",
    "Command library"
  ],
  [
    "Выбери один или несколько наборов. Уже существующие команды не дублируются.",
    "Select one or more command sets. Existing commands will not be duplicated."
  ],
  [
    "Добавить выбранные",
    "Add selected"
  ],
  [
    "Добавлено команд: ",
    "Commands added: "
  ],
  [
    "; пропущено повторов: ",
    "; duplicates skipped: "
  ],
  [
    "Если сигнал не принимается, попробуй повторить обучение при выключенном телевизоре. Если Remote unavailable, восстанови LAN-соединение с хабом. HTTP 400 означает ошибку, а не успешное обучение.",
    "If the signal is not received, try learning again with the TV switched off. If the remote is unavailable, restore the hub's LAN connection. HTTP 400 is an error, not a successful learning result."
  ],
  [
    "Импорт ИК-кода:",
    "Import IR code:"
  ],
  [
    "Вставь точную строку кода DP202, полученную от этого локального Tuya IR Hub. Не вставляй Local Key или Device ID.",
    "Paste the exact DP202 code string received from this local Tuya IR Hub. Do not paste the Local Key or Device ID."
  ],
  [
    "Вставь RAW Base64 (u16 little-endian). Код сохранится исключительно в IR Studio. Не вставляй Cloud Key ID или Local Key.",
    "Paste RAW Base64 (u16 little-endian). It will be stored only in IR Studio, not the external remote. Never paste a Local Key."
  ],
  [
    "Импорт сохраняет код локально, но не подтверждает физическую реакцию устройства.",
    "Import stores the code locally but does not verify the device's physical response."
  ],
  [
    "Сохранить ИК-код",
    "Save IR code"
  ],
  [
    "Добавить набор команд",
    "Add command set"
  ],
  [
    "Выбери набор целиком или отметь отдельные команды. Уже существующие команды не дублируются.",
    "Choose a whole set or select individual commands. Existing commands will not be duplicated."
  ],
  [
    "Выбрать отдельные команды",
    "Choose individual commands"
  ],
  [
    "Выбрать все наборы",
    "Select all sets"
  ],
  [
    "Выбери одну или несколько команд",
    "Select one or more commands"
  ],
  [
    "Выбери наборы или отдельные команды",
    "Select command sets or individual commands"
  ],
  [
    "Неизвестная команда в библиотеке",
    "Unknown command in the library"
  ],
  [
    "Экспортировано ",
    "Exported "
  ],
  [
    " пультов · RAW-кодов ",
    " remotes · IR payloads "
  ],
  [
    "Обучить",
    "Learn"
  ],
  [
    "Послать",
    "Send"
  ],
  [
    "Внести RAW-код этой кнопки",
    "Import RAW code for this command"
  ],
  [
    "Удалить запись из списка; raw-код останется",
    "Remove from list; stored IR code will remain"
  ],
  [
    "Шаблон устройства не найден",
    "Device template was not found"
  ],
  [
    "Выбери один или несколько наборов команд",
    "Select one or more command sets"
  ],
  [
    "Неизвестный или повторяющийся набор команд",
    "Unknown or duplicate command set"
  ],
  [
    "Достигнут лимит 200 команд на пульт",
    "The 200-command limit for this remote has been reached"
  ],
  [
    "Импорт Tuya DP202 требует нативный Remote ИК Студии",
    "Tuya DP202 import requires a native IR Studio remote"
  ],
  [
    "RAW-код хранится только в IR Studio, внешние Remote не изменяются",
    "RAW is stored only in IR Studio; external remotes are not modified"
  ],
  [
    "IR Studio не имеет доступа к хранилищу другого Remote",
    "IR Studio does not access foreign remote code stores"
  ],
  [
    "Неподдерживаемый формат ИК-кода",
    "Unsupported IR payload format"
  ]
].sort((a,b)=>b[0].length-a[0].length);

class IRStudioPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: 'open'});
    this.shadowRoot.addEventListener('click', (event) => this._handleClick(event));
    this.shadowRoot.addEventListener('keydown', (event) => this._handleProfileDragKeydown(event));
    this.shadowRoot.addEventListener('pointerdown', (event) => this._dragPointerDown(event));
    this.shadowRoot.addEventListener('pointermove', (event) => this._dragPointerMove(event));
    this.shadowRoot.addEventListener('pointerup', (event) => this._dragPointerUp(event));
    this.shadowRoot.addEventListener('pointercancel', () => this._clearDrag());
    this._drag = null;
    this._hass = null;
    this._data = null;
    this._active = null;
    this._filter = '';
    this._pending = null;
    this._learnWizard = null;
    this._batchStarting = false;
    this._commandAddBusy = false;
    this._advancedMode = false;
    this._poller = null;
    this._pollBusy = false;
    this._accountChoices = [];
    this._notice = '';
    this._busy = false;
    this._installed = false;
    this._selectedSource = '';
    this._importBackup = null;
  }

  set hass(value) {
    this._hass = value;
    if (!this._installed && value) {
      this._installed = true;
      this._load();
    } else if (this._installed) {
      this._refreshAvailability();
    }
  }
  set narrow(value) { this._narrow = value; }
  set route(value) { this._route = value; }
  set panel(value) { this._panel = value; }

  disconnectedCallback() { if (this._poller) clearInterval(this._poller); }

  async _call(type, extra = {}) {
    if (!this._hass?.connection) throw new Error('Нет WebSocket-сессии Home Assistant');
    return this._hass.connection.sendMessagePromise({type:'ir_studio/' + type, ...extra});
  }

  _language() {
    const value = this._hass?.locale?.language || this._hass?.language || document.documentElement.lang || navigator.language || 'en';
    return String(value).toLowerCase().startsWith('ru') ? 'ru' : 'en';
  }

  _label(value) {
    if (typeof value === 'string') return value;
    return value?.[this._language()] || value?.en || value?.ru || '';
  }

  _translateText(value) {
    if (this._language() !== 'en') return value;
    let result = String(value ?? '');
    for (const [source, target] of EN_TEXT) result = result.replaceAll(source, target);
    return result;
  }

  _localize(root) {
    if (this._language() !== 'en' || !root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.parentElement?.closest('[data-no-translate]')) continue;
      node.nodeValue = this._translateText(node.nodeValue);
    }
    for (const element of root.querySelectorAll?.('[placeholder],[title],[aria-label]') || []) {
      if (element.closest('[data-no-translate]')) continue;
      for (const attr of ['placeholder', 'title', 'aria-label']) {
        if (element.hasAttribute(attr)) element.setAttribute(attr, this._translateText(element.getAttribute(attr)));
      }
    }
  }

  _setHTML(root, markup) {
    root.innerHTML = markup;
    this._localize(root);
  }

  _findTemplate(templateId) {
    const catalog = this._data?.template_catalog || {};
    for (const category of catalog.categories || []) {
      const found = (category.templates || []).find(item => item.id === templateId);
      if (found) return found;
    }
    return null;
  }

  _commandSuggestions() {
    // Suggestions are names only, never invented IR signals.
    return Object.values(this._data?.template_catalog?.commands || {})
      .map(item => item?.labels?.en)
      .filter(value => typeof value === 'string' && value)
      .sort((a, b) => a.localeCompare(b));
  }

  _showButtonLibrary() {
    const sets = this._data?.template_catalog?.button_sets || [];
    const commands = this._data?.template_catalog?.commands || {};
    const options = sets.map(item => {
      const name = this._label(item.labels);
      const description = this._label(item.descriptions);
      const individual = item.buttons.map(commandId => {
        const command = commands[commandId];
        return `<label class="command-choice"><input type="checkbox" data-command-choice="${h(commandId)}" /><span>${h(command?.labels?.en || commandId)}</span></label>`;
      }).join('');
      return `<div class="set-card"><label class="set-option"><input type="checkbox" data-set-choice="${h(item.id)}" /><span><b>${h(name)}</b><small>${h(description)} · ${item.buttons.length}</small></span></label><details><summary>Выбрать отдельные команды</summary><div class="command-pick-list">${individual}</div></details></div>`;
    }).join('');
    this._dialog(`<h3>Библиотека команд</h3><p class="muted">Выбери набор целиком или отметь отдельные команды. Уже существующие команды не дублируются.</p><input class="library-search" id="library-search" type="search" placeholder="Поиск команд: MODE, RGB…" aria-label="Поиск в библиотеке" autocomplete="off" /><div class="set-list">${options}</div><div class="row" style="margin-top:10px"><button data-action="button-sets-select-all">Выбрать все наборы</button><button data-action="button-sets-select-none">Снять выбор</button></div><div class="dialog-footer"><button data-action="close-modal">Отмена</button><button class="primary" data-action="add-button-sets">Добавить выбранные</button></div>`);
    this.shadowRoot.querySelector('#library-search')?.addEventListener('input', event => {
      const term = event.target.value.trim().toLocaleLowerCase();
      this.shadowRoot.querySelectorAll('.set-card').forEach(card => {
        const group = card.querySelector('.set-option')?.textContent?.toLocaleLowerCase().includes(term);
        let visible = 0;
        card.querySelectorAll('.command-choice').forEach(choice => {
          const show = !term || group || choice.textContent?.toLocaleLowerCase().includes(term);
          choice.hidden = !show;
          if (show) visible++;
        });
        card.hidden = Boolean(term && !group && !visible);
        if (term && visible && !group) card.querySelector('details').open = true;
      });
    });
  }

  async _load() {
    try {
      this._data = await this._call('get');
      setIconCatalog(this._data.icons);
      if (!this._pending) {
        const live = (this._data.jobs || []).findLast(job =>
          job.kind === 'learn' && ['running', 'cancelling'].includes(job.status));
        if (live && this._data.profiles.some(p => p.id === live.profile_id)) {
          this._active = live.profile_id;
          this._pending = {
            id: live.id, kind: live.kind, buttonId: live.button_id,
            profileId: live.profile_id,
            started: (live.started_at || Date.now() / 1000) * 1000,
            timeout: Number(live.timeout || 60), cancelling: live.status === 'cancelling',
          };
          this._startJobPolling();
        }
      }
      if (!this._active || !this._data.profiles.some((p) => p.id === this._active))
        this._active = this._data.profiles[0]?.id || null;
      this._render();
      this._updateLearningCountdown();
    } catch (e) { this._renderError('Не удалось получить настройки: ' + (e.message || String(e))); }
  }

  _remotes() {
    // Profile remotes represent appliances and must never be chosen as their
    // own transmitter (or as the transmitter of another virtual remote).
    return Object.entries(this._hass?.states || {}).filter(([id, state]) =>
      id.startsWith('remote.') && !state.attributes?.ir_studio_virtual)
      .map(([id, state]) => ({id, name:state.attributes?.friendly_name || id, status:state.state}));
  }

  _defaultRemoteId() {
    // 'off' is a normal idle state for HA Remote (including Tuya Local).
    // Never automatically select an unavailable/unknown entity.
    const usable=this._remotes().filter(r=>['on','off'].includes(r.status));
    if(!usable.length)return '';
    // Honor an explicit manual choice while that entity remains usable.
    if(this._selectedSource && usable.some(r=>r.id===this._selectedSource))
      return this._selectedSource;
    // Keep the current profile's already configured LAN executor when possible.
    const current=this._selected()?.remote_entity;
    if(current && usable.some(r=>r.id===current))return current;
    return usable.find(r=>r.status==='on')?.id || usable[0].id;
  }

  _selected() { return this._data?.profiles.find(p => p.id === this._active); }
  _remOptions(value) {
    return this._remotes().map(r =>
      `<option data-no-translate value="${h(r.id)}" ${r.id===value?'selected':''}>${h(r.name)} (${h(r.id)} · ${h(r.status)})</option>`
    ).join('') || '<option value="">Нет локальных remote-сущностей — сначала добавь ИК-драйвер в Home Assistant</option>';
  }

  _renderError(msg) {
    this._setHTML(this.shadowRoot, `<div style="padding:36px; font-family:sans-serif">${h(msg)}<p><a href="/config/integrations">Открыть интеграции HA</a></p></div>`);
  }

  _render() {
    const data = this._data;
    if (!data) return;
    const profile = this._selected();
    const remote = profile && this._hass?.states[profile.remote_entity];
    const remoteState = remote?.state || 'не найдена';
    // For a Remote entity, only "on" is healthy. "off", "unknown" and
    // "unavailable" must not be rendered as a green/healthy connection.
    const remoteClass = ['on', 'off'].includes(remoteState) ? 'good' : 'bad';
    const profileList = data.profiles.map(p => {
      const progress = profileLearningSummary(p.buttons);
      const summary = progress.needsCheck
        ? `${progress.accounted} из ${progress.total} обучено/восстановлено · ${progress.needsCheck} проверить`
        : `${progress.learned} из ${progress.total} обучено`;
      return `
      <div class="profile-entry" data-profile-row="${h(p.id)}">
        <button type="button" class="profile ${p.id===this._active?'active':''}" data-action="select" data-profile="${h(p.id)}">
          <span class="profile-symbol" aria-hidden="true">${profileGlyph(p)}</span>
          <span class="profile-copy"><b data-no-translate>${h(p.name)}</b>
            <small title="Восстановленные из резервной копии команды учитываются отдельно от физически проверенных.">${h(summary)}</small></span>
          <span class="profile-chevron" aria-hidden="true">›</span>
        </button>
        ${data.profiles.length > 1 ? `<div class="profile-controls">
          <button type="button" class="profile-drag-handle drag-handle" data-profile-drag="${h(p.id)}"
            aria-keyshortcuts="ArrowUp ArrowDown"
            aria-label="${h(this._language()==='ru'?'Изменить порядок пульта '+p.name:'Reorder remote '+p.name)}"
            title="${h(this._language()==='ru'?'Перетащить или использовать стрелки клавиатуры':'Drag or use keyboard arrow keys')}">⠿</button>
        </div>` : ''}
      </div>`;
    }).join('');
    const css = `
      :host{display:block;box-sizing:border-box;color:var(--primary-text-color,#e5e7eb);background:var(--primary-background-color,#111827);min-height:100vh;font:14px system-ui,sans-serif}
      *{box-sizing:border-box} .shell{max-width:1440px;margin:auto;padding:20px 24px 70px}
      h1{font-size:25px;letter-spacing:-.5px;margin:0 0 6px} h2{font-size:19px;margin:0 0 14px} h3{font-size:16px;margin:0 0 10px} p{line-height:1.5}
      .muted{color:var(--secondary-text-color,#9ca3af)} .tiny{font-size:12px} .top{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}
      .logo{width:34px;height:34px;object-fit:contain;vertical-align:middle;margin-right:8px} .grid{display:grid;grid-template-columns:260px minmax(0,1fr);gap:16px;align-items:start}
      .card{background:var(--card-background-color,#1f2937);border:1px solid var(--divider-color,#374151);border-radius:15px;padding:18px;margin-bottom:14px;box-shadow:0 1px 2px #0001}
      .panel-note{border-left:3px solid var(--info-color,#38bdf8);padding:10px 14px;background:var(--secondary-background-color,#182331);border-radius:8px;margin-bottom:16px;line-height:1.55}
      .profile{background:transparent;border:1px solid transparent;color:inherit;display:flex;width:100%;justify-content:space-between;text-align:left;gap:8px;padding:11px 10px;cursor:pointer;border-radius:9px}
      .profile:hover{background:var(--secondary-background-color,#303a48)} .profile.active{border-color:var(--primary-color,#38bdf8);background:var(--secondary-background-color,#303a48)} .profile-name{font-weight:650} small{color:var(--secondary-text-color,#9ca3af);white-space:nowrap}
      button{cursor:pointer;border-radius:9px;padding:9px 13px;border:1px solid var(--divider-color,#4b5563);background:var(--secondary-background-color,#263241);color:inherit;font:inherit}
      button:hover{border-color:var(--primary-color,#38bdf8)} button.primary{background:var(--primary-color,#0891b2);color:white;border-color:transparent;font-weight:650} button.danger{color:var(--error-color,#ef4444)} button:disabled{opacity:.45;cursor:not-allowed}
      input,select,textarea{background:var(--input-fill-color,#121b2a);border:1px solid var(--divider-color,#465161);border-radius:8px;color:inherit;padding:10px;width:100%;font:inherit;min-width:0}
      select{cursor:pointer;color-scheme:inherit} select option{background:var(--card-background-color,#1f2937);color:var(--primary-text-color,#e5e7eb)} label{display:block;color:var(--secondary-text-color,#b2bbc6);font-size:12px;font-weight:600;margin:11px 0 5px}
      .actions{display:flex;flex-wrap:wrap;gap:7px;align-items:center}.actions button{padding:7px 10px;font-size:13px}.pill{border-radius:100px;padding:3px 8px;background:var(--secondary-background-color,#293746);color:var(--secondary-text-color,#aab5c5);white-space:nowrap;font-size:12px}
      .pill.ok{color:#52d2a2}.pill.warn{color:#ffc56d}.pill.err{color:#fb7185}.headrow{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
      .table{display:grid;gap:0}.item{display:grid;grid-template-columns:minmax(100px,1fr) 150px auto;gap:10px;align-items:center;padding:10px 4px;border-top:1px solid var(--divider-color,#344054)} .item:first-child{border-top:0}
      .item b{overflow-wrap:anywhere}.status{display:flex;align-items:center;gap:5px;justify-content:flex-start}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.row > :is(input,select){flex:1}.bar{display:flex;gap:8px;flex-wrap:wrap}
      .row-main{min-width:0}.row-tools{display:flex;gap:5px;align-items:center;margin-top:5px}
      button.icon-btn,button.drag-handle{width:24px;height:24px;min-width:24px;padding:0;display:inline-flex;align-items:center;justify-content:center;line-height:1}
      button.icon-btn{font-size:12px}.drag-handle{font-size:17px;cursor:grab;touch-action:none;user-select:none;color:var(--secondary-text-color,#aab5c5)}
      .drag-handle:active{cursor:grabbing}.item.dragging{opacity:.42}.item.drop-before{box-shadow:inset 0 3px 0 var(--primary-color,#38bdf8)}
      .item.drop-after{box-shadow:inset 0 -3px 0 var(--primary-color,#38bdf8)}
      .warning{color:#f7c97c}.connect{font-size:12px}.connect.bad{color:#fb7185}.connect.good{color:#34d399}
      .overlay{position:fixed;inset:0;background:#0009;display:flex;align-items:center;justify-content:center;padding:18px;z-index:12}
      .dialog{background:var(--card-background-color,#1e293b);border:1px solid var(--divider-color,#475569);border-radius:18px;max-width:580px;width:100%;padding:22px;box-shadow:0 24px 70px #0006}
      .dialog h3{font-size:19px}.template-preview{margin:10px 0;padding:10px;border:1px solid var(--divider-color,#374151);border-radius:9px}.template-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}.set-list{display:grid;gap:7px;max-height:48vh;overflow:auto}.set-card{border:1px solid var(--divider-color,#374151);border-radius:9px;padding:7px}.set-card .set-option{border:0;padding:5px}.set-card details{padding:4px 8px 8px}.set-card summary{cursor:pointer;color:var(--secondary-text-color);font-size:12px} select option,select optgroup{background:var(--card-background-color,#202020);color:var(--primary-text-color,#eee)}.command-pick-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:4px;margin-top:8px}.command-choice{display:flex;align-items:center;gap:7px;margin:0;padding:4px 6px;border-radius:6px}.command-choice input{width:15px;min-width:15px;accent-color:var(--primary-color,#0891b2)}.set-option{display:flex;gap:10px;align-items:flex-start;padding:10px;border:1px solid var(--divider-color,#374151);border-radius:9px;margin:0}.set-option input{width:17px;min-width:17px;margin-top:3px;accent-color:var(--primary-color,#0891b2)}.set-option span{display:grid;gap:3px}.set-option small{white-space:normal} .subline{font-size:13px;color:var(--secondary-text-color,#9ca3af)} .backup-row{display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--divider-color,#374151)} .backup-row input{width:17px;height:17px;flex:none;accent-color:var(--primary-color,#0891b2)} .backup-option{display:flex;gap:8px;align-items:center} .backup-option label{margin:0} .toast{position:fixed;right:24px;bottom:24px;max-width:min(420px,85vw);background:var(--card-background-color,#1f2937);border:1px solid var(--divider-color,#374151);border-radius:10px;padding:14px 18px;z-index:10000;box-shadow:0 8px 32px #0006;line-height:1.4} .dialog-footer{margin-top:17px;display:flex;justify-content:flex-end;gap:8px}
      .banner{padding:13px;border:1px solid var(--divider-color,#475569);border-radius:10px;margin-top:10px;line-height:1.5;background:var(--secondary-background-color,#263343)}
      .account-import-button{border:1px solid var(--primary-color,#38bdf8);background:linear-gradient(120deg,rgba(14,165,233,.12),rgba(124,58,237,.12));border-radius:10px}
      .account-import-button:hover{background:linear-gradient(120deg,rgba(14,165,233,.21),rgba(124,58,237,.2))}
      .account-choice{display:flex;align-items:center;gap:10px;border:1px solid var(--divider-color,#475569);border-radius:11px;padding:10px;margin:6px 0}
      .account-choice input{width:17px;min-width:17px;accent-color:var(--primary-color,#38bdf8)}
      .account-choice small{display:block;color:var(--secondary-text-color,#94a3b8);margin-top:3px}
      .account-choices{max-height:40vh;overflow:auto;margin:12px 0}
      .account-choice.unverified{opacity:.66;border-style:dashed}
      .account-device-row{padding:7px 10px;margin:7px 0;border:1px solid var(--divider-color,#475569);border-radius:12px;background:linear-gradient(110deg,rgba(14,165,233,.045),rgba(124,58,237,.055))}
      .account-device-row .account-choice{padding:6px;border:0;background:transparent;margin:0;min-width:0}
      .account-device-row .cloud-remote-copy{min-width:0;flex:1}
      .account-device-row .cloud-remote-copy small{display:block;line-height:1.45;white-space:normal}
      .account-device-commands{margin:0 0 2px 40px;color:var(--secondary-text-color,#94a3b8)}
      .account-device-commands summary{font-size:12px;font-weight:650;cursor:pointer;padding:4px 0}
      .account-command-chips{display:flex;gap:5px;flex-wrap:wrap;padding:6px 0 9px}
      .account-command-chips span{display:inline-flex;padding:4px 7px;border-radius:7px;border:1px solid var(--divider-color,#475569);font-size:11px;color:var(--primary-text-color,#e5e7eb)}
      .account-device-row .field-hint{padding:3px 0 7px 40px}

      .dialog{max-height:min(86vh,950px);overflow:auto;background:
        radial-gradient(ellipse at top right,rgba(139,92,246,.10),transparent 65%),
        radial-gradient(ellipse at top left,rgba(14,165,233,.075),transparent 58%),
        var(--card-background-color,#1e293b)}
      .dialog h3{display:flex;align-items:center;gap:8px;letter-spacing:-.2px}
      .dialog .set-card{background:linear-gradient(116deg,rgba(14,165,233,.048),rgba(139,92,246,.045));
        border-radius:12px;padding:10px;border:1px solid var(--divider-color,#374151);
        transition:border-color .17s,background .17s}
      .dialog .set-card:hover{border-color:var(--primary-color,#38bdf8);
        background:linear-gradient(116deg,rgba(14,165,233,.10),rgba(139,92,246,.075))}
      .dialog .set-option{padding:6px;gap:11px}
      .dialog .set-option b{font-size:13px}
      .dialog .set-option small{font-size:11px;white-space:normal;line-height:1.45}
      .dialog .set-card summary{padding:7px 9px;border-radius:7px;outline-offset:2px}
      .dialog .set-card summary:hover{background:rgba(14,165,233,.07)}
      .dialog .command-choice{border:1px solid transparent;border-radius:9px;min-height:34px}
      .dialog .command-choice:hover{background:rgba(14,165,233,.10);
        border-color:color-mix(in srgb,var(--primary-color,#38bdf8) 25%,transparent)}
      .dialog-footer{position:sticky;bottom:-22px;padding:14px 0 0;
        background:var(--card-background-color,#1e293b);z-index:1}
      .dialog button.primary{background:linear-gradient(115deg,var(--primary-color,#0891b2),#5577e8)}
      .dialog:focus-within{border-color:color-mix(in srgb,var(--primary-color,#38bdf8) 43%,var(--divider-color,#374151))}
      @media(max-width:550px){.overlay{padding:8px}.dialog{border-radius:15px;padding:16px;
        max-height:95vh}.dialog-footer{bottom:-16px}.set-list{max-height:48vh}}
      .account-identity{font-size:11px;margin-top:4px}
      .import-evidence{display:grid;gap:7px;padding:14px;margin:13px 0;
        border:1px solid color-mix(in srgb,var(--primary-color,#38bdf8) 40%,var(--divider-color,#374151));
        border-radius:13px;background:linear-gradient(125deg,rgba(14,165,233,.1),rgba(124,58,237,.09))}
      .import-evidence strong{font-size:13px}.import-evidence span{font-size:12px}
      .import-evidence small{color:var(--secondary-text-color,#94a3b8);font-size:11px;line-height:1.5}
      .learn-countdown{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--primary-color,#38bdf8);border-radius:26px;padding:3px 9px 3px 3px;background:linear-gradient(135deg,rgba(14,165,233,.12),rgba(124,58,237,.12));cursor:pointer}
      .learn-clock{display:grid;place-items:center;width:37px;height:37px;border-radius:50%;background:conic-gradient(var(--primary-color,#38bdf8) var(--progress),rgba(148,163,184,.25) 0);font-variant-numeric:tabular-nums}
      .learn-seconds{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:var(--card-background-color,#1e293b);color:var(--primary-text-color,#fff);font-size:13px;font-weight:700}
      .learn-caption{font-size:11px;font-weight:600}
      .learn-countdown:focus-visible{outline:2px solid var(--primary-color,#38bdf8);outline-offset:2px}
      .studio-intro{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:17px}
      .studio-intro span{border:1px solid var(--divider-color,#374151);border-radius:999px;background:linear-gradient(115deg,rgba(14,165,233,.085),rgba(124,58,237,.085));padding:8px 13px;font-size:12px;font-weight:600}
      .top{padding:19px 22px;border:1px solid var(--divider-color,#374151);border-radius:18px;background:radial-gradient(ellipse at 12% -40%,rgba(14,165,233,.2),transparent 55%),radial-gradient(ellipse at 95% 0%,rgba(139,92,246,.13),transparent 45%),var(--card-background-color,#1f2937)}
      .card{box-shadow:0 7px 22px rgba(0,0,0,.08);transition:border-color .18s,box-shadow .18s}
      .card:hover{border-color:color-mix(in srgb,var(--primary-color,#38bdf8) 24%,var(--divider-color,#374151))}
      button.primary{background:linear-gradient(115deg,var(--primary-color,#0891b2),#5577e8);box-shadow:0 3px 11px rgba(14,165,233,.13)}
      button.primary:hover{filter:brightness(1.08);transform:translateY(-1px)}
      .profile-entry{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:5px;border-radius:10px}
      .profile-entry.dragging{opacity:.45}
      .profile-entry.drop-before{box-shadow:inset 0 3px 0 var(--primary-color,#38bdf8)}
      .profile-entry.drop-after{box-shadow:inset 0 -3px 0 var(--primary-color,#38bdf8)}
      .profile-entry:focus-within{outline:1px solid color-mix(in srgb,var(--primary-color,#38bdf8) 45%,transparent)}
      .profile{min-width:0;align-items:center;gap:10px;transition:background .17s,border-color .17s,transform .17s}
      .profile-controls{display:flex;align-items:center;justify-content:center}
      .profile-controls .profile-drag-handle{min-width:30px;width:30px;height:38px;padding:0;display:grid;place-items:center;line-height:1;font-size:18px;touch-action:none;cursor:grab}
      .profile-controls .profile-drag-handle:active{cursor:grabbing}
      .profile-controls .profile-drag-handle:focus-visible{outline:2px solid var(--primary-color,#38bdf8);outline-offset:2px}
      .profile{align-items:center;gap:10px;transition:background .17s,border-color .17s,transform .17s}
      .profile:hover{transform:translateX(2px)}
      .profile.active{background:linear-gradient(115deg,rgba(14,165,233,.13),rgba(139,92,246,.11));border-color:var(--primary-color,#38bdf8)}
      .profile-symbol{--studio-icon-size:23px;width:35px;height:35px;display:grid;place-items:center;flex:none;border-radius:10px;background:var(--secondary-background-color,#293746)}
      .device-icon{display:grid;place-items:center;--mdc-icon-size:var(--studio-icon-size,23px);width:var(--studio-icon-size,23px);height:var(--studio-icon-size,23px);flex:none;line-height:0;color:var(--primary-color,#38bdf8)}
      .icon-picker{border:1px solid var(--divider-color,#465161);border-radius:12px;overflow:hidden}
      .icon-picker-empty{font-size:22px;font-weight:400;color:var(--secondary-text-color,#9ca3af)}
      .icon-picker-summary{display:flex;align-items:center;gap:12px;cursor:pointer;padding:9px 12px;list-style:none}
      .icon-picker-summary::-webkit-details-marker{display:none}
      .icon-picker-summary>span:nth-child(2){flex:1;font-size:13px;font-weight:650}
      .icon-picker-summary small{display:block;font-size:11px;font-weight:400;margin-top:3px}
      .icon-picker-content{padding:12px;border-top:1px solid var(--divider-color,#374151)}
      .icon-picker-content input{margin-bottom:10px}
      .icon-catalog{max-height:300px;overflow:auto;overscroll-behavior:contain}
      .icon-group[hidden],.icon-choice[hidden]{display:none!important}
      .icon-group h4{font-size:11px;letter-spacing:.06em;margin:14px 0 7px;color:var(--secondary-text-color,#9ca3af)}
      .icon-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(86px,1fr));gap:7px}
      button.icon-choice{display:flex;align-items:center;flex-direction:column;justify-content:center;gap:6px;min-height:80px;padding:10px 5px;border-radius:11px;text-align:center}
      .icon-choice{--studio-icon-size:27px}
      .icon-choice span{font-size:10px;line-height:1.2;overflow-wrap:anywhere}
      .icon-choice[aria-pressed="true"]{border:2px solid var(--primary-color,#38bdf8);background:rgba(14,165,233,.16)}
      .empty-state-icon{--studio-icon-size:40px;display:grid;place-items:center}
      .cloud-remote-icon{--studio-icon-size:24px}
      .type-selector{display:flex;align-items:stretch;gap:9px}
      .type-selector select{min-width:0;flex:1}
      .type-preview{--studio-icon-size:25px;display:grid;place-items:center;flex:0 0 45px;border-radius:11px;
        border:1px solid color-mix(in srgb,var(--primary-color,#38bdf8) 35%,var(--divider-color,#374151));
        background:linear-gradient(135deg,rgba(14,165,233,.12),rgba(139,92,246,.12))}
      .profile-copy{min-width:0;display:grid;gap:2px;flex:1}
      .profile-copy b{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .profile-copy small{font-size:11px}
      .profile-chevron{font-size:21px;opacity:.6}
      .profile-heading{display:flex;align-items:center;gap:13px;min-width:0}
      .profile-heading h2{margin:0 0 6px}
      .profile-heading-glyph{--studio-icon-size:36px;display:grid;place-items:center;width:53px;height:53px;flex:none;border:1px solid var(--divider-color,#374151);border-radius:14px;background:linear-gradient(130deg,rgba(14,165,233,.13),rgba(124,58,237,.15))}
      .connection-chip{display:inline-flex;gap:6px;border-radius:999px;padding:4px 9px;background:var(--secondary-background-color,#293746);font-size:11px}
      .connection-chip.good{color:#34d399}.connection-chip.bad{color:#fb7185}
      .remote-details{display:flex;flex-wrap:wrap;align-items:center;gap:9px;margin-top:16px;color:var(--secondary-text-color,#94a3b8);font-size:12px}
      .remote-details span:last-child{padding:5px 9px;border:1px solid var(--divider-color,#374151);border-radius:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
      .settings-button{background:linear-gradient(115deg,rgba(14,165,233,.12),rgba(139,92,246,.1));border-color:var(--primary-color,#38bdf8)}
      .command-add-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:15px 0}
      .command-add-bar input{flex:1;min-width:170px}
      .dialog .library-search{margin:9px 0 12px;min-height:43px;border-radius:11px}
      .dialog .command-choice[hidden],.dialog .set-card[hidden]{display:none}
      .empty-state{border:1px dashed var(--divider-color,#374151);border-radius:15px;text-align:center;padding:35px 18px;margin-top:11px;background:linear-gradient(135deg,rgba(14,165,233,.05),rgba(124,58,237,.07))}
      .empty-state-icon{font-size:34px;margin-bottom:10px}
      .empty-state h3{font-size:16px;margin-bottom:5px}
      .empty-state p{max-width:400px;margin:8px auto 17px;color:var(--secondary-text-color,#94a3b8)}
      .empty-state .primary{display:inline-block}
      .settings-note{border-radius:9px;border:1px solid var(--divider-color,#374151);padding:11px;background:var(--secondary-background-color,#293746);font-size:12px;color:var(--secondary-text-color,#94a3b8);margin-top:13px}
      .settings-note b{color:var(--primary-text-color,#eee)}
      .modal-heading{display:flex;align-items:center;gap:13px;margin:0 0 18px;padding:0 0 16px;border-bottom:1px solid var(--divider-color,#374151)}
      .modal-heading-icon{--studio-icon-size:30px;display:grid;place-items:center;flex:0 0 50px;width:50px;height:50px;border:1px solid rgba(56,189,248,.25);border-radius:14px;background:linear-gradient(135deg,rgba(14,165,233,.16),rgba(124,58,237,.17));color:var(--primary-color,#38bdf8)}
      .modal-heading-copy{display:grid;gap:3px;min-width:0}
      .modal-eyebrow{font-size:10px;font-weight:800;letter-spacing:.12em;color:var(--primary-color,#38bdf8)}
      .dialog .modal-heading h3{font-size:20px;line-height:1.2;margin:0;letter-spacing:-.35px}
      .modal-heading p{margin:1px 0 0;color:var(--secondary-text-color,#9ca3af);font-size:12px;line-height:1.45}
      .form-stack{display:grid;gap:15px}
      .form-field{display:grid;gap:7px;min-width:0}
      .form-field label{margin:0;color:var(--primary-text-color,#e5e7eb);font-size:12px;font-weight:700}
      .form-field input,.form-field select{min-height:45px;border-radius:11px;background:linear-gradient(180deg,rgba(15,23,42,.48),rgba(15,23,42,.24));border-color:color-mix(in srgb,var(--divider-color,#475569) 78%,white 22%)}
      .form-field input:focus,.form-field select:focus{outline:none;border-color:var(--primary-color,#38bdf8);box-shadow:0 0 0 3px rgba(56,189,248,.12)}
      .field-hint{display:block;color:var(--secondary-text-color,#94a3b8);font-size:11px;line-height:1.45;white-space:normal}
      .type-selector{gap:10px}
      .type-preview{flex-basis:49px;min-height:46px}
      .type-selector select{min-height:46px}
      .form-note{display:flex;align-items:flex-start;gap:10px;margin-top:15px;padding:12px 13px;border:1px solid color-mix(in srgb,var(--primary-color,#38bdf8) 28%,var(--divider-color,#374151));border-radius:13px;background:linear-gradient(120deg,rgba(14,165,233,.075),rgba(124,58,237,.07))}
      .form-note.is-warning{border-color:rgba(251,191,36,.32);background:linear-gradient(120deg,rgba(245,158,11,.09),rgba(124,58,237,.045))}
      .form-note-icon{display:grid;place-items:center;flex:0 0 28px;width:28px;height:28px;border-radius:9px;background:rgba(56,189,248,.13);color:#7dd3fc;font-weight:800}
      .form-note.is-warning .form-note-icon{background:rgba(245,158,11,.15);color:#fbbf24}
      .form-note strong{display:block;font-size:12px;color:var(--primary-text-color,#e5e7eb)}
      .form-note p{margin:3px 0 0;color:var(--secondary-text-color,#aab5c5);font-size:11px;line-height:1.5}
      .cloud-state{display:grid;gap:7px;padding:14px;border:1px solid color-mix(in srgb,var(--primary-color,#38bdf8) 30%,var(--divider-color,#374151));border-radius:13px;background:linear-gradient(120deg,rgba(14,165,233,.09),rgba(124,58,237,.08))}
      .cloud-state.is-error{border-color:rgba(251,113,133,.38);background:linear-gradient(120deg,rgba(244,63,94,.09),rgba(124,58,237,.055))}
      .cloud-state-title{font-size:13px;font-weight:750}
      .cloud-state p{margin:0;color:var(--secondary-text-color,#c0c8d4);font-size:12px;line-height:1.55;white-space:normal}
      .cloud-state-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
      .cloud-state-tag{display:inline-flex;align-items:center;border:1px solid rgba(56,189,248,.25);border-radius:999px;padding:4px 8px;color:#7dd3fc;background:rgba(14,165,233,.09);font-size:9px;font-weight:800;letter-spacing:.08em}
      .cloud-state-meta{display:flex;flex-wrap:wrap;gap:7px;margin-top:3px}
      .cloud-state-meta span{font-size:10px;color:var(--secondary-text-color,#94a3b8);border:1px solid var(--divider-color,#374151);border-radius:7px;padding:4px 7px}
      .cloud-loading{min-height:190px;display:grid;align-content:center;gap:13px}
      .cloud-loading .modal-heading{margin-bottom:5px}
      .cloud-loading-line{display:flex;align-items:center;gap:11px;padding:12px;border:1px solid var(--divider-color,#374151);border-radius:12px;background:rgba(14,165,233,.045)}
      .cloud-loading-line>div{display:grid;gap:3px}
      .cloud-loading-line b{font-size:12px}
      .cloud-loading-line small{font-size:11px;white-space:normal}
      .cloud-spinner{width:22px;height:22px;flex:none;border:2px solid rgba(56,189,248,.2);border-top-color:#38bdf8;border-right-color:#8b5cf6;border-radius:50%;animation:ir-studio-spin .8s linear infinite}
      @keyframes ir-studio-spin{to{transform:rotate(360deg)}}
      .cloud-profile-target{display:flex;align-items:center;gap:10px;padding:10px 12px;margin-bottom:12px;border:1px solid var(--divider-color,#374151);border-radius:12px;background:linear-gradient(120deg,rgba(14,165,233,.06),rgba(124,58,237,.06))}
      .cloud-profile-glyph{display:grid;place-items:center;width:38px;height:38px;border-radius:10px;background:rgba(14,165,233,.12)}
      .cloud-profile-target .device-icon{width:22px;height:22px}
      .cloud-profile-target>span:last-child{display:grid;gap:3px}
      .cloud-profile-target small{font-size:9px;letter-spacing:.1em;font-weight:800;color:var(--secondary-text-color,#94a3b8)}
      .cloud-profile-target b{font-size:13px}
      .cloud-selection-tools{margin-top:12px}
      .cloud-key-list{margin-top:10px}
      .dialog-footer{gap:9px;flex-wrap:wrap}
      @media(max-width:550px){.dialog{padding:16px}.modal-heading-icon{flex-basis:43px;width:43px;height:43px}.dialog .modal-heading h3{font-size:18px}.dialog-footer button{flex:1}}
      /* One visual language: command rows are cards like profile settings. */
      .table{gap:9px}
      .item{border:1px solid var(--divider-color,#374151)!important;border-radius:13px;
        padding:13px 14px;background:linear-gradient(118deg,
          rgba(14,165,233,.035),rgba(139,92,246,.035));
        transition:border-color .17s,background .17s,transform .17s}
      .item:hover{border-color:color-mix(in srgb,var(--primary-color,#38bdf8) 38%,var(--divider-color,#374151))!important;
        background:linear-gradient(120deg,rgba(14,165,233,.085),rgba(139,92,246,.065))}
      .item .row-main{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
      .item .row-main>b{font-size:14px;letter-spacing:.08px}
      .item .row-tools{margin:0;display:inline-flex;gap:3px;opacity:.68}
      .item:hover .row-tools,.item:focus-within .row-tools{opacity:1}
      .item .actions{justify-content:flex-end}
      .item .actions button{border-radius:9px;min-height:34px}
      .item .actions [data-action="learn-modal"]{background:linear-gradient(115deg,
        rgba(14,165,233,.19),rgba(99,102,241,.20));border-color:rgba(56,189,248,.5);
        color:var(--primary-text-color,#fff);font-weight:650}
      .item .actions [data-action="learn-modal"]:hover{background:linear-gradient(115deg,
        rgba(14,165,233,.28),rgba(99,102,241,.28))}
      .item .actions [data-action="send"]:not(:disabled){border-color:rgba(52,211,153,.4);
        background:rgba(52,211,153,.08)}
      .item .status .pill{border:1px solid var(--divider-color,#374151);padding:5px 10px;
        font-size:11px;letter-spacing:.1px}
      .item .actions [data-action="delete-button"]{background:rgba(244,63,94,.06)}
      .cloud-remote-list{display:grid;gap:9px;max-height:46vh;overflow:auto;margin:15px 0}
      .cloud-remote-card{display:flex;align-items:center;gap:11px;width:100%;text-align:left;
        background:linear-gradient(115deg,rgba(14,165,233,.08),rgba(139,92,246,.08));
        border:1px solid var(--divider-color,#374151);padding:12px 13px;border-radius:13px}
      .cloud-remote-card:hover{border-color:var(--primary-color,#38bdf8)}
      .cloud-remote-icon{font-size:23px;display:grid;place-items:center;width:38px;height:38px;
        border-radius:10px;background:rgba(14,165,233,.12)}
      .cloud-remote-copy{display:grid;flex:1;gap:4px;min-width:0}
      .cloud-remote-copy small{font-size:11px}
      .cloud-key-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
        gap:8px;max-height:42vh;overflow:auto;margin:14px 0}
      .cloud-key-choice{display:flex;align-items:center;gap:9px;margin:0;padding:10px;
        border-radius:10px;border:1px solid var(--divider-color,#374151);
        background:linear-gradient(115deg,rgba(14,165,233,.055),rgba(139,92,246,.055))}
      .cloud-key-choice:hover{border-color:var(--primary-color,#38bdf8)}
      .cloud-key-choice input{width:18px;min-width:18px;accent-color:var(--primary-color,#38bdf8)}
      .cloud-key-choice span{min-width:0;display:grid;gap:3px}
      .cloud-key-choice small{font-size:11px}
      .cloud-info{border:1px solid color-mix(in srgb,var(--primary-color,#38bdf8) 35%,var(--divider-color,#374151));
        border-radius:12px;padding:13px;display:grid;gap:6px;
        background:linear-gradient(115deg,rgba(14,165,233,.11),rgba(139,92,246,.08))}
      .cloud-info p{margin:3px 0}.cloud-info small{line-height:1.5;white-space:normal}
      .cloud-source-tag{display:inline-flex;align-items:center;gap:4px;
        border-radius:999px;padding:4px 7px;font-size:10px;white-space:nowrap;
        border:1px solid rgba(56,189,248,.24);background:rgba(14,165,233,.095);
        color:var(--secondary-text-color,#aabbcc)}
      .cloud-loading{min-height:135px;display:grid;align-content:center;gap:8px}
      .cloud-loading small{color:var(--secondary-text-color,#94a3b8)}
      .cloud-loading p{margin:0}
      @media(max-width:700px){.item{grid-template-columns:minmax(0,1fr)!important;gap:9px}
        .item .actions{justify-content:flex-start;grid-column:auto!important}
        .item .status{grid-column:auto!important}
        .cloud-key-list{grid-template-columns:1fr}}
      button{transition:filter .16s,transform .16s,border-color .16s}
      button:focus-visible{outline:2px solid var(--primary-color,#38bdf8);outline-offset:2px}
      @media(prefers-reduced-motion:reduce){.learn-countdown,.learn-clock,.card,.profile,.item,button{transition:none!important;animation:none!important;transform:none!important}}
      @media(max-width:650px){.top{padding:14px}.studio-intro span{font-size:11px}.command-add-bar input{flex-basis:100%}.profile-heading-glyph{--studio-icon-size:29px;width:43px;height:43px}.remote-details{margin-top:10px}}
      a{color:var(--primary-color,#38bdf8);text-decoration:none} .toolbar{display:flex;gap:8px;flex-wrap:wrap} .search{max-width:220px}
      @media(max-width:800px){.grid{grid-template-columns:1fr}.shell{padding:12px}.item{grid-template-columns:1fr auto}.status{grid-column:1/3}.item .actions{grid-column:1/3}}
      /* Tactile controls: one visual language across toolbar, cards and dialogs. */
      button:not(.profile):not(.cloud-remote-card):not(.primary):not(.danger):not(.account-import-button):not(.settings-button){
        border-color:color-mix(in srgb,var(--divider-color,#475569) 68%,white 32%);
        background:linear-gradient(180deg,
          color-mix(in srgb,var(--card-background-color,#252932) 88%,white 12%),
          color-mix(in srgb,var(--card-background-color,#252932) 94%,black 6%));
        box-shadow:inset 0 1px 0 rgba(255,255,255,.075),0 2px 5px rgba(0,0,0,.14);
        font-weight:560;letter-spacing:.005em;
      }
      button:not(.profile):not(.cloud-remote-card):not(.settings-button):not(.account-import-button):not(:disabled){
        transition:background .18s,border-color .18s,box-shadow .18s,transform .18s,filter .18s;
      }
      button:not(.profile):not(.cloud-remote-card):not(.settings-button):not(.account-import-button):not(:disabled):hover{
        border-color:color-mix(in srgb,var(--primary-color,#38bdf8) 64%,white 36%);
        background:linear-gradient(180deg,
          color-mix(in srgb,var(--primary-color,#38bdf8) 13%,var(--card-background-color,#252932)),
          color-mix(in srgb,var(--primary-color,#38bdf8) 7%,var(--card-background-color,#252932)));
        box-shadow:inset 0 1px 0 rgba(255,255,255,.1),0 5px 13px rgba(14,165,233,.13);
        transform:translateY(-1px);
      }
      button:not(.profile):not(.cloud-remote-card):not(.settings-button):not(.account-import-button):not(:disabled):active{
        transform:translateY(0) scale(.975);box-shadow:inset 0 2px 5px rgba(0,0,0,.2);
      }
      button.primary{
        border:1px solid rgba(125,211,252,.34);
        background:linear-gradient(112deg,#0891b2 0%,#3478e5 58%,#7255d9 100%);
        color:#fff;font-weight:700;letter-spacing:.01em;
        box-shadow:inset 0 1px 0 rgba(255,255,255,.24),
          0 4px 13px rgba(37,99,235,.24),0 0 0 1px rgba(56,189,248,.08);
      }
      button.primary:hover:not(:disabled){
        background:linear-gradient(112deg,#06a6c8 0%,#4388f4 58%,#8568ed 100%);
        box-shadow:inset 0 1px 0 rgba(255,255,255,.3),
          0 7px 19px rgba(37,99,235,.3),0 0 0 3px rgba(56,189,248,.08);
        filter:none;transform:translateY(-1px);
      }
      .dialog button.primary{
        background:linear-gradient(112deg,#0891b2 0%,#3478e5 58%,#7255d9 100%);
        border:1px solid rgba(125,211,252,.34);
        box-shadow:inset 0 1px 0 rgba(255,255,255,.24),0 4px 13px rgba(37,99,235,.24);
      }
      .dialog button.primary:hover:not(:disabled){
        background:linear-gradient(112deg,#06a6c8 0%,#4388f4 58%,#8568ed 100%);
        box-shadow:inset 0 1px 0 rgba(255,255,255,.3),0 7px 19px rgba(37,99,235,.3);
      }
      button.primary:active:not(:disabled){transform:translateY(0) scale(.98)}
      button.danger{
        border-color:rgba(251,113,133,.28);
        background:linear-gradient(180deg,rgba(244,63,94,.12),rgba(190,24,93,.07));
        color:var(--error-color,#fb7185);
        box-shadow:inset 0 1px 0 rgba(255,255,255,.045);
      }
      button.danger:hover:not(:disabled){
        border-color:rgba(251,113,133,.62);
        background:linear-gradient(180deg,rgba(244,63,94,.2),rgba(190,24,93,.13));
        box-shadow:0 4px 12px rgba(225,29,72,.12);
      }
      button:disabled{
        opacity:.42;cursor:not-allowed;filter:saturate(.55);
        transform:none!important;box-shadow:none!important;
      }
      button:focus-visible{
        outline:2px solid var(--primary-color,#38bdf8);outline-offset:3px;
        box-shadow:0 0 0 5px rgba(56,189,248,.12);
      }
      button.account-import-button,button.settings-button{
        border:1px solid rgba(56,189,248,.42);
        background:linear-gradient(120deg,rgba(14,165,233,.16),rgba(99,102,241,.16),rgba(124,58,237,.12));
        box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 3px 9px rgba(14,165,233,.1);
      }
      button.account-import-button:hover:not(:disabled),button.settings-button:hover:not(:disabled){
        background:linear-gradient(120deg,rgba(14,165,233,.25),rgba(99,102,241,.24),rgba(124,58,237,.2));
        border-color:rgba(56,189,248,.72);box-shadow:0 6px 15px rgba(14,165,233,.16);
        transform:translateY(-1px);
      }
      .toolbar button{min-height:40px;border-radius:12px;padding:9px 15px}
      .actions button{border-radius:10px}
      .item .actions button[data-action="learn-modal"]{
        background:linear-gradient(115deg,rgba(14,165,233,.2),rgba(99,102,241,.23));
        border-color:rgba(56,189,248,.52);color:var(--primary-text-color,#fff);font-weight:700;
      }
      .item .actions button[data-action="learn-modal"]:hover:not(:disabled){
        background:linear-gradient(115deg,rgba(14,165,233,.3),rgba(99,102,241,.32));
        box-shadow:0 5px 14px rgba(14,165,233,.16);
      }
      .item .actions button[data-action="send"]:not(:disabled){
        background:linear-gradient(115deg,rgba(16,185,129,.16),rgba(20,184,166,.13));
        border-color:rgba(52,211,153,.4);color:var(--primary-text-color,#fff);
      }
      .item .actions button[data-action="delete-button"]{
        background:linear-gradient(115deg,rgba(244,63,94,.13),rgba(190,24,93,.08));
        border-color:rgba(251,113,133,.24);color:var(--error-color,#fb7185);
      }
      .item .actions button[data-action="delete-button"]:hover:not(:disabled){
        background:linear-gradient(115deg,rgba(244,63,94,.22),rgba(190,24,93,.16));
        border-color:rgba(251,113,133,.55);
      }
      .dialog-footer button{min-height:39px;border-radius:11px;padding:9px 15px}
      button.icon-btn,button.drag-handle{
        border-radius:8px;background:linear-gradient(145deg,rgba(148,163,184,.12),rgba(71,85,105,.12));
        border-color:rgba(148,163,184,.16);
      }
      .cloud-remote-card{
        position:relative;overflow:hidden;
        box-shadow:inset 0 1px 0 rgba(255,255,255,.06),0 3px 10px rgba(0,0,0,.12);
        transition:transform .18s,border-color .18s,box-shadow .18s;
      }
      .cloud-remote-card:hover{
        transform:translateY(-2px);
        border-color:color-mix(in srgb,var(--primary-color,#38bdf8) 72%,white 28%);
        box-shadow:0 8px 20px rgba(14,165,233,.13);
      }
      .cloud-remote-icon{border:1px solid rgba(56,189,248,.17)}
      @media(prefers-reduced-motion:reduce){
        button,.cloud-remote-card{transition:none!important;transform:none!important}
      }
    `;
    this._setHTML(this.shadowRoot, `
      <style>${css}</style>
      <div class="shell">
        <div class="top"><div><h1><img class="logo" src="/ir_studio_static/icon.png" alt="" />Tuya IR Studio</h1><div class="muted">Локальные ИК-пульты · Home Assistant</div></div>
          <div class="toolbar"><button data-action="refresh">↻ Обновить</button><button data-action="open-backup">⇅ Резервная копия</button></div>
        </div>
        <div class="studio-intro"><span>✦ Локальное управление</span><span>◷ 60 секунд на обучение</span><span>◈ Коды хранятся локально</span></div>
        <div class="grid">
          <aside>
            <div class="card"><h3>Пульты</h3>${profileList || '<p class="muted">Пока нет профилей</p>'}
              <button class="primary" style="width:100%;margin-top:12px" data-action="new-profile" ${this._remotes().length ? '' : 'disabled'}>+ Добавить пульт</button>
            </div>
          </aside>
          <main>${profile ? `
            <section class="card">
              <div class="headrow"><div class="profile-heading">
                <span class="profile-heading-glyph" aria-hidden="true">${profileGlyph(profile)}</span>
                <div><h2 data-no-translate>${h(profile.name)}</h2>
                  <span class="connection-chip ${remoteClass}">● ${h(remoteState)} · LAN</span>
                </div></div>
                <div class="actions"><button class="settings-button" data-action="profile-settings">⚙ Настройки</button>
                  ${profile.buttons.some(b => b.status === 'pending' && !b.verified &&
                    b.code_in_local_store === false)
                    ? '<button data-action="review-unlearned" title="Удалить только выбранные клавиши без ИК-кодов">◻ Очистить пустые</button>' : ''}
                  </div></div>
              <div class="remote-details"><span>Исполнитель</span><span data-no-translate title="${h(profile.remote_entity)}">${h(this._hass?.states[profile.remote_entity]?.attributes?.friendly_name || profile.remote_entity)}</span></div>

            </section>
            <section class="card">
              <div class="headrow"><div><h2>Команды <span class="pill">${profile.buttons.length}</span></h2>
                <div class="muted tiny">Создай нужные команды и обучи их оригинальным пультом через локальный шлюз.</div></div>
                <input class="search" id="filter" placeholder="Поиск кнопки…" value="${h(this._filter)}" /></div>
              ${this._learningGuide(profile)}
              <div class="command-add-bar"><input id="new-button" list="library-command-suggestions" placeholder="Название команды: MODE, RGB…" maxlength="96" autocomplete="off" aria-label="Новая команда с подсказками" /><datalist id="library-command-suggestions">${this._commandSuggestions().map(name => `<option value="${h(name)}"></option>`).join("")}</datalist>
                <button data-action="new-button">+ Добавить</button>
                <button data-action="button-library">⊞ Библиотека</button></div>
              <div id="command-list" class="table"></div>
            </section>` : `
            <div class="card"><h2>Выбери пульт или добавь новый</h2><p class="muted">Для создания профиля нужна локальная HA remote-сущность физического ИК-драйвера.</p>
              <button class="primary" data-action="new-profile" ${this._remotes().length ? '' : 'disabled'}>Добавить первый пульт</button></div>`}</main>
        </div>
        <div id="modal"></div>
      </div>`);
    const filter = this.shadowRoot.querySelector('#filter');
    if (filter) filter.oninput = (e) => {this._filter=e.target.value; this._renderRows();};
    const addInput = this.shadowRoot.querySelector('#new-button');
    if (addInput) addInput.onkeydown = event => {
      if (event.key === 'Enter' && !event.isComposing) {
        event.preventDefault();
        void this._addCommandFromInput();
      }
    };
    this._renderRows();
  }

  _buttonsNeedingLearning(profile) {
    // Real code-store flags always win over old metadata statuses. Never
    // repeat training for already learned or physically verified commands.
    return (profile?.buttons || []).filter(button =>
      !button.verified &&
      button.code_in_local_store !== true &&
      button.code_in_tuya_ir_store !== true &&
      (button.code_in_local_store === false ||
       button.code_in_tuya_ir_store === false ||
       button.status === 'pending'));
  }

  _learningGuide(profile) {
    if (!profile) return '';
    const wizard = this._learnWizard?.profileId === profile.id
      ? this._learnWizard : null;
    if (!wizard) {
      const missing = this._buttonsNeedingLearning(profile);
      if (!missing.length) return '';

      return `<div class="form-note" style="margin:12px 0">
        <span class="form-note-icon" aria-hidden="true">i</span>
        <div><strong>Необученные кнопки: ${missing.length}</strong>
          <p>Обучи нужные кнопки оригинальным пультом через локальный шлюз.
            Сохранённые ИК-коды не нужно обучать повторно.</p>
          <button class="primary" data-action="learn-all" ${this._pending ? 'disabled' : ''}
            style="margin-top:8px">Обучить по порядку (${missing.length})</button>
        </div>
      </div>`;
    }
    const total = wizard.buttonIds.length;
    const currentId = wizard.buttonIds[wizard.index];
    const current = profile.buttons.find(b => b.id === currentId);
    if (!current || wizard.index >= total) {
      return `<div class="form-note" style="margin:12px 0">
        <span class="form-note-icon" aria-hidden="true">✓</span>
        <div><strong>Обучение завершено</strong>
          <p>Получено: ${wizard.completed}, пропущено: ${wizard.skipped}. Сигналы сохраняются в Home Assistant, их не нужно импортировать повторно.</p>
          <button class="primary" data-action="learn-finish">Готово</button>
        </div>
      </div>`;
    }
    const learning = this._pending?.kind === 'learn' &&
      this._pending.profileId === profile.id &&
      this._pending.buttonId === currentId;
    const label = wizard.index + 1;
    return `<div class="form-note" style="margin:12px 0">
      <span class="form-note-icon" aria-hidden="true">◷</span>
      <div><strong>Обучение ${label} из ${total}: <span data-no-translate>${h(current.name)}</span></strong>
        <p>${learning
          ? 'Направь оригинальный пульт на ИК-шлюз и нажми указанную кнопку. У тебя до 60 секунд.'
          : this._batchStarting ? 'Запускаем приём сигнала…' : 'Приготовь оригинальный пульт. Нажми «Продолжить», затем эту же кнопку на пульте.'}</p>
        ${wizard.lastResult ? `<p>${h(wizard.lastResult)}</p>` : ''}
        <div class="row" style="margin-top:8px">
          ${learning
            ? '<span class="muted">Ожидаем ИК-сигнал… Таймер и отмена — в строке команды ниже.</span>'
            : this._batchStarting ? '<span class="muted">Подключаем приём ИК…</span>'
            : `<button class="primary" data-action="learn-next" ${this._pending ? 'disabled' : ''}>Продолжить обучение</button>
               <button data-action="learn-skip" ${this._pending ? 'disabled' : ''}>Пропустить</button>`}
          ${wizard.stopRequested
            ? '<span class="muted">Завершаем обучение после подтверждения запуска…</span>'
            : '<button data-action="learn-finish">Завершить</button>'}
        </div>
      </div>
    </div>`;
  }

  async _beginBatchLearning() {
    const profile = this._selected();
    if (!profile || this._pending || this._learnWizard) return;
    const missing = this._buttonsNeedingLearning(profile);
    if (!missing.length) return this._toast('Все кнопки уже обучены');
    this._learnWizard = {
      profileId: profile.id, buttonIds: missing.map(b => b.id),
      index: 0, completed: 0, skipped: 0, lastResult: '',
    };
    this._filter = '';
    // First click must launch the first IR receiver, not just display Continue.
    // Begin just the first command. Between commands require a user click
    // so a lingering press cannot be accidentally saved as the next code.
    await this._batchLearnNext();
  }

  async _batchLearnNext() {
    const wizard = this._learnWizard;
    const profile = this._selected();
    if (!wizard || !profile || profile.id !== wizard.profileId ||
        this._pending || this._batchStarting) return;
    const buttonId = wizard.buttonIds[wizard.index];
    if (!buttonId) return;
    const button = profile.buttons.find(b => b.id === buttonId);
    if (!button) {
      wizard.lastResult = 'Кнопка удалена; пропускаем.';
      wizard.skipped++;
      wizard.index++;
      this._render();
      return;
    }
    wizard.lastResult = '';
    this._batchStarting = true;
    this._render();
    try {
      if (!await this._start('learn', buttonId)) {
        wizard.lastResult = 'Не удалось запустить приём. Можно повторить или пропустить.';
      }
    } finally {
      this._batchStarting = false;
      // Finish may be requested while the WebSocket start RPC is in flight.
      // If the job started, cancel it now rather than leaving an invisible
      // receiver running after the user already closed the guide.
      if (wizard.stopRequested && this._learnWizard === wizard)
        await this._batchLearnFinish();
      else
        this._render();
    }
  }

  _batchLearnSkip() {
    const wizard = this._learnWizard;
    if (!wizard || wizard.stopRequested || this._batchStarting ||
        this._pending || wizard.index >= wizard.buttonIds.length) return;
    wizard.index++;
    wizard.skipped++;
    wizard.lastResult = '';
    this._render();
  }

  async _batchLearnFinish() {
    const wizard = this._learnWizard;
    if (!wizard) return;
    if (this._batchStarting) {
      // The server may not have returned the job ID yet. Keep the wizard
      // attached and cancel the exact job as soon as the start RPC resolves.
      wizard.stopRequested = true;
      this._render();
      return;
    }
    // Ending the guide must not leave an invisible receiver running.
    if (this._pending?.kind === 'learn' && this._pending.profileId === wizard.profileId)
      await this._cancelLearning();
    if (this._learnWizard === wizard) {
      this._learnWizard = null;
      this._render();
    }
  }

  _renderRows() {
    const host = this.shadowRoot.querySelector('#command-list');
    const p = this._selected();
    if (!host || !p) return;
    if (!p.buttons.length) {
      const glyph = profileGlyph(p);
      this._setHTML(host, `<div class="empty-state">
        <div class="empty-state-icon" aria-hidden="true">${glyph}</div>
        <h3>Пульт пока пустой</h3>
        <p>Добавь нужные кнопки вручную или выбери их из библиотеки,
           затем обучи оригинальным пультом через локальный ИК-шлюз.</p>
        <button class="primary" data-action="button-library">⊞ Выбрать команды</button>
      </div>`);
      return;
    }
    const lines = p.buttons.filter(b => b.name.toLowerCase().includes(this._filter.toLowerCase()));
    this._setHTML(host, lines.map(b => {
      const known = b.code_in_local_store === true || b.code_in_tuya_ir_store === true;
      const status = b.verified ? ['ok','Физически проверено'] : known ? ['ok','Код сохранён'] : b.status === 'needs_check' ? ['warn','Требуется проверка'] : b.status === 'stored' && p.source === 'tuya_local' ? ['ok','Сохранено в Tuya Local'] : b.status === 'stored' ? ['warn','Сохранение заявлено'] : ['','Не обучена'];
      return `<div class="item" data-button-row="${h(b.id)}">
        <div class="row-main"><b data-no-translate>${h(b.name)}</b>
          <div class="row-tools">
          <button class="drag-handle" type="button" data-drag-handle="${h(b.id)}" aria-label="Перетащить ${h(b.name)}" title="Перетащить для изменения порядка">⠿</button>
          <button class="icon-btn" type="button" data-action="rename-button" data-button="${h(b.id)}" aria-label="Переименовать ${h(b.name)}" title="Переименовать">✎</button>
        </div></div>
        <span class="status"><span class="pill ${status[0]}">${status[1]}</span></span>
        <div class="actions">
          ${this._pending?.kind === 'learn' && this._pending.buttonId === b.id
            ? `<button class="learn-countdown" type="button" data-action="cancel-job"
                 data-button="${h(b.id)}" title="Нажми на таймер, чтобы отменить"
                 aria-label="Отменить обучение ${h(b.name)}">
                 <span class="learn-clock" style="--progress:100%"><span class="learn-seconds">60</span></span>
                 <span class="learn-caption">${this._pending.cancelling ? 'Останавливаем…' : 'Отменить'}</span>
               </button>`
            : `<button data-action="learn-modal" data-button="${h(b.id)}"
                ${this._pending?.kind === 'learn' ? 'disabled' : ''}>Обучить</button>`}
          <button data-action="send" data-button="${h(b.id)}" ${(!known && !['needs_check','stored','verified'].includes(b.status))?'disabled':''}>Послать</button>

          <button class="danger" data-action="delete-button" data-button="${h(b.id)}" title="Удалить кнопку и её код из хранилища IR Studio">×</button>
        </div></div>`;
    }).join('') || '<p class="muted">Ничего не найдено</p>');
  }

  _refreshAvailability() {
    const p = this._selected();
    const badge = this.shadowRoot.querySelector('span.connect');
    if (!p || !badge) return;
    const state = this._hass?.states[p.remote_entity]?.state || 'не найдена';
    badge.textContent = '● ' + this._translateText(state);
    badge.className = 'connect ' + (['on', 'off'].includes(state) ? 'good' : 'bad');
  }

  _dialog(inner) {
    const el = this.shadowRoot.querySelector('#modal');
    if (!el) return;
    this._setHTML(el, `<div class="overlay" role="dialog" aria-modal="true"><div class="dialog">${inner}</div></div>`);
    el.querySelector('.overlay').onclick = (e) => {if(e.target.classList.contains('overlay')) this._dialogClose();};
  }
  _dialogClose() {const el=this.shadowRoot.querySelector('#modal');if(el) el.innerHTML='';}

  _showRenameProfile() {
    const p=this._selected(); if(!p)return;
    this._dialog(`<h3>Переименовать пульт</h3>
      <label>Новое название</label><input id="rename-profile-name" maxlength="64" value="${h(p.name)}" />
      <p class="tiny muted">Существующие ИК-коды сохранят прежний внутренний ключ и останутся доступными.</p>
      <div class="dialog-footer"><button data-action="close-modal">Отмена</button><button class="primary" data-action="save-profile-name">Сохранить</button></div>`);
  }

  _showRenameButton(btnId) {
    const p=this._selected(),b=p?.buttons.find(x=>x.id===btnId);if(!b)return;
    this._dialog(`<h3>Переименовать кнопку</h3>
      <label>Новое название</label><input id="rename-button-name" maxlength="96" value="${h(b.name)}" />
      <p class="tiny muted">Внутреннее имя команды Remote не меняется — ранее обученный код не потеряется.</p>
      <div class="dialog-footer"><button data-action="close-modal">Отмена</button><button class="primary" data-action="save-button-name" data-button="${h(b.id)}">Сохранить</button></div>`);
  }

  _iconPickerMarkup(prefix,current) {
  const lang=this._language();
  const icons=this._data?.icons || [];
  const groups=[
    ['video','Видео и ТВ','Video & TV'],
    ['audio','Аудиотехника','Audio'],
    ['climate','Климат','Climate'],
    ['lighting','Освещение','Lighting'],
    ['home','Дом и управление','Home & control'],
    ['appliance','Бытовая техника','Appliances'],
  ];
  const selected=current && icons.some(i=>i.id===current) ? current : '';
  const content=groups.map(([group,ru,en])=>{
    const tiles=icons.filter(i=>i.group===group).map(i=>{
      const title=i.labels?.[lang] || i.labels?.en || i.id;
      const search=`${i.labels?.ru} ${i.labels?.en} ${i.id}`.toLowerCase();
      return `<button type="button" class="icon-choice" data-action="choose-icon"
        data-icon-choice="${h(i.id)}" data-icon-search="${h(search)}"
        aria-label="${h(title)}" aria-pressed="${i.id===selected}">${deviceIcon(i.id)}
        <span data-no-translate>${h(title)}</span></button>`;
    }).join('');
    return `<section class="icon-group"><h4>${h(lang==='ru'?ru:en)}</h4>
      <div class="icon-grid">${tiles}</div></section>`;
  }).join('');
  return `<div class="icon-picker">
    <input type="hidden" id="${h(prefix)}-icon" value="${h(selected)}" data-selected-icon>
    <details><summary class="icon-picker-summary">
      <span class="type-preview" data-icon-preview>${selected?deviceIcon(selected):'<span class="icon-picker-empty" aria-hidden="true">+</span>'}</span>
      <span data-icon-picker-caption>${selected?h(icons.find(i=>i.id===selected)?.labels?.[lang]||'Иконка выбрана'):'Выбрать иконку'}<small>Без изменения ИК-команд</small></span>
      <span aria-hidden="true">⌄</span></summary>
      <div class="icon-picker-content">
        <input type="search" id="${h(prefix)}-icon-search" placeholder="Поиск иконки…" aria-label="Поиск иконки">
        <div class="icon-catalog">${content}</div>
      </div></details></div>`;
}

  _wireIconPicker(prefix) {
  const modal=this.shadowRoot?.querySelector('#modal');
  const input=modal?.querySelector(`#${prefix}-icon-search`);
  input?.addEventListener?.('input',()=>{
    const term=input.value.trim().toLowerCase();
    for(const tile of modal.querySelectorAll('[data-icon-choice]'))
      tile.hidden=!(tile.dataset.iconSearch||'').includes(term);
    for(const section of modal.querySelectorAll('.icon-group'))
      section.hidden=!section.querySelector('.icon-choice:not([hidden])');
  });
}

  _showProfileSettings() {
  const p=this._selected();
  if(!p)return;
  setIconCatalog(this._data?.icons);
  const current=p.icon||profileTemplateId(p);
  this._dialog(`${modalHeading(deviceIcon(current),'НАСТРОЙКИ ПРОФИЛЯ','Настройки пульта','Измени название, иконку или локальный исполнитель.')}
    <div class="form-stack">
      <div class="form-field"><label for="settings-name">Название пульта</label>
        <input id="settings-name" value="${h(p.name)}" maxlength="64" /></div>
      <div class="form-field"><label>Иконка пульта</label>
        ${this._iconPickerMarkup('settings',current)}
        <small class="field-hint">Иконка меняет только внешний вид. Кнопки и ИК-сигналы не меняются.</small></div>
      <div class="form-field"><label for="settings-remote">Локальный исполнитель</label>
        <select id="settings-remote">${this._remOptions(p.remote_entity)}</select>
        <small class="field-hint">При смене исполнителя коды прежнего драйвера не переносятся.</small></div>
      <details class="form-field" style="padding:10px 0">
        <summary style="cursor:pointer">Дополнительно: загрузка файла ИК-сигналов</summary>
        <p class="muted tiny">Основной способ — обучить команды оригинальным пультом. Импорт совместимого файла .ir необязателен.</p>
        ${p.source==='ir_studio'?'<button type="button" data-action="ir-file-open">Загрузить файл .ir</button>':''}
      </details>
    </div>
    <div class="form-note"><span class="form-note-icon" aria-hidden="true">✓</span>
      <div><strong>Сохранность ИК-кодов</strong><p>Изменение иконки не затрагивает обученные команды.</p></div>
    </div>
    <div class="dialog-footer">
      <button class="danger" data-action="delete-profile">Удалить пульт</button>
      <button data-action="close-modal">Отмена</button>
      <button class="primary" data-action="save-profile-settings">Сохранить настройки</button>
    </div>`);
  this._wireIconPicker('settings');
}

  async _saveProfileSettings() {
  const p=this._selected();
  const modal=this.shadowRoot.querySelector('#modal');
  if(!p||!modal)return;
  const name=modal.querySelector('#settings-name')?.value?.trim();
  const icon=modal.querySelector('#settings-icon')?.value;
  const entity_id=modal.querySelector('#settings-remote')?.value;
  if(!name||!icon||!entity_id||!ICON_BY_ID.has(icon)){
    this._toast('Укажи название, иконку и ИК-шлюз',true);
    return;
  }
  if(entity_id!==p.remote_entity&&!window.confirm('Коды прежнего драйвера не переносятся. Сменить шлюз?'))return;
  try {
    if(icon!==(p.icon||profileTemplateId(p)))
      await this._call('profile_set_icon',{profile_id:p.id,icon});
    if(name!==p.name)
      await this._call('profile_rename',{profile_id:p.id,name});
    if(entity_id!==p.remote_entity)
      await this._call('profile_bind',{profile_id:p.id,entity_id});
    this._dialogClose();
    await this._load();
    this._toast('Настройки сохранены · ИК-коды не изменены');
  } catch(error){
    await this._load();
    this._toast('Ошибка настроек: '+(error.message||String(error)),true);
  }
}

  _showReviewUnlearned() {
    const profile = this._selected();
    if (!profile) return;
    // Unknown remote drivers are excluded because only a real negative
    // store result proves a local code is absent.
    const candidates = profile.buttons.filter(button =>
      button.status === 'pending' && !button.verified &&
      button.code_in_local_store === false
    );
    if (!candidates.length) {
      this._toast('Нет кнопок с подтверждённым отсутствием ИК-кодов');
      return;
    }
    const choices = candidates.map(button => `
      <label class="account-choice">
        <input type="checkbox" data-cleanup-id="${h(button.id)}" />
        <span data-no-translate>${h(button.name)}
          <small>Не обучена · локальный код отсутствует</small></span>
      </label>`).join('');
    this._dialog(`<h3>◻ Проверить необученные кнопки</h3>
      <div class="import-evidence">
        <strong>Очистка только по твоему выбору</strong>
        <span>Отметь ненужные заготовки. Обученные, импортированные или
          неизвестные драйверу коды сервер удалять не позволит.</span>
      </div>
      <div class="row"><button data-action="cleanup-all">Выбрать все необученные</button>
        <button data-action="cleanup-none">Снять выбор</button></div>
      <div class="account-choices">${choices}</div>
      <div class="dialog-footer"><button data-action="close-modal">Отмена</button>
        <button class="danger" data-action="cleanup-selected">Удалить выбранные</button></div>`);
  }

  async _cleanupSelected() {
    const profile = this._selected();
    const modal = this.shadowRoot.querySelector('#modal');
    const button_ids = [...(modal?.querySelectorAll('[data-cleanup-id]:checked') || [])]
      .map(el=>el.dataset.cleanupId);
    if (!profile || !button_ids.length) {
      this._toast('Отметь кнопки для удаления', true);
      return;
    }
    if (!window.confirm(`Удалить ${button_ids.length} необученных кнопок?
Сохранённые ИК-коды и неизвестные драйверу команды сервер защитит.`)) return;
    try {
      const result = await this._call('profile_remove_unlearned', {
        profile_id: profile.id, button_ids,
      });
      this._dialogClose();
      await this._load();
      this._toast(`Удалено заготовок: ${result.removed}; сохранённых кодов: 0.`);
    } catch (error) {
      this._toast('Очистка не выполнена: ' + (error.message || String(error)), true);
      await this._load();
    }
  }

  _updateCreateProfileValidity(){
    const modal=this.shadowRoot?.querySelector('#modal');
    if(!modal)return false;
    const name=modal.querySelector('#profile-name')?.value?.trim();
    const icon=modal.querySelector('#create-icon')?.value;
    const entity=modal.querySelector('#profile-remote')?.value;
    const valid=Boolean(name && icon && ICON_BY_ID.has(icon) && entity &&
      this._remotes().some(r=>r.id===entity));
    const submit=modal.querySelector('[data-action="create-profile"]');
    if(submit)submit.disabled=!valid;
    return valid;
  }

  _showCreateProfile(){
  setIconCatalog(this._data?.icons);

  const hasRemotes=this._remotes().length>0;
  const defaultRemote=this._defaultRemoteId();
  const warning=hasRemotes?'':`<div class="form-note is-warning"><span class="form-note-icon" aria-hidden="true">!</span>
    <div><strong>Нет локального ИК-шлюза</strong><p>Добавь локальную HA remote-сущность через Настройки → Устройства и службы.</p></div></div>`;
  this._dialog(`${modalHeading(deviceIcon('blank_remote'),'НОВЫЙ ПРОФИЛЬ','Добавить пульт','Выбери иконку и локальный ИК-шлюз.')}
    <div class="form-stack">
      <div class="form-field"><label for="profile-name">Название пульта</label>
        <input id="profile-name" value="" placeholder="Название пульта" maxlength="64" autocomplete="off" required /></div>
      <div class="form-field"><label>Иконка пульта</label>
        ${this._iconPickerMarkup('create','')}
        <small class="field-hint">Выбор иконки не создаёт кнопки или ИК-коды.</small></div>
      <div class="form-field"><label for="profile-remote">Локальный исполнитель</label>
        <select id="profile-remote" required>${defaultRemote ? '' : '<option value="" selected disabled>Выбрать ИК-шлюз</option>'}${this._remOptions(defaultRemote)}</select>
        <small class="field-hint">${defaultRemote
          ? 'Доступный ИК-шлюз выбран автоматически. При необходимости выбери другой.'
          : 'Выбери доступный локальный ИК-шлюз.'}</small></div>
    </div>
    ${warning}
    <div class="form-note"><span class="form-note-icon" aria-hidden="true">✓</span>
      <div><strong>Команды и ИК-сигналы</strong>
        <p>После создания выбери английские команды из библиотеки и обучи их оригинальным пультом.</p></div></div>
    <div class="dialog-footer"><button data-action="close-modal">Отмена</button>
      <button class="primary" data-action="create-profile" disabled>Добавить пульт</button></div>`);
  this._wireIconPicker('create');
  const modal=this.shadowRoot?.querySelector('#modal');
  modal?.querySelector('#profile-name')?.addEventListener?.('input',()=>this._updateCreateProfileValidity());
  modal?.querySelector('#profile-remote')?.addEventListener?.('change',()=>{
    const chosen=modal.querySelector('#profile-remote')?.value;
    if(chosen && this._remotes().some(r=>r.id===chosen))this._selectedSource=chosen;
    this._updateCreateProfileValidity();
  });
  this._updateCreateProfileValidity();
}

  _showIrFileImport() {
    const profile = this._selected();
    if (!profile || profile.source !== 'ir_studio') {
      this._toast('Выбери профиль, подключённый к нативному Remote IR Studio', true);
      return;
    }
    this._irFileContent = null;
    this._irFileProfile = profile.id;
    this._dialog(`<h3>Загрузить сигналы из файла · ${h(profile.name)}</h3>
      <p>Этот способ нужен, только если у тебя уже есть файл с ИК-сигналами именно для твоей модели устройства.</p>
      <p><strong>Нет такого файла?</strong> Закрой окно и используй «Обучить по порядку» — это основной способ.</p>
      <p class="muted tiny">Для опытных пользователей: поддерживаются файлы Flipper .ir (RAW 38 кГц, NEC, NECext).
      Обученные кнопки не перезаписываются. Данные остаются в Home Assistant.</p>
      <input id="ir-profile-file" type="file" accept=".ir,text/plain" style="display:none">
      <div class="dialog-footer">
        <button data-action="close-modal">Закрыть</button>
        <button class="primary" data-action="ir-file-pick">Выбрать файл</button>
      </div>`);
    const input = this.shadowRoot.querySelector('#ir-profile-file');
    if (input) input.onchange = e => this._previewIrFile(e.target.files?.[0]);
  }

  async _previewIrFile(file) {
    if (!file) return;
    if (file.size > 200000 || !file.name.toLowerCase().endsWith('.ir')) {
      this._toast('Нужен файл .ir не больше 200 КБ', true);
      return;
    }
    const p = this._selected();
    if (!p || p.id !== this._irFileProfile) return;
    try {
      const content = await file.text();
      const preview = await this._call('ir_file_preview', {profile_id:p.id,content});
      const available = Array.isArray(preview.supported_names) ? preview.supported_names : [];
      const unsupported = Array.isArray(preview.unsupported) ? preview.unsupported : [];
      if (!available.length) {
        this._toast('В файле нет поддерживаемых ИК-сигналов RAW 38 кГц / NEC / NECext', true);
        return;
      }
      this._irFileContent = content;
      const normalize = name => String(name || '').trim().toLowerCase().replace(/[ _-]+/g, '');
      const used = new Set();
      const rows = available.map(name => {
        const matches = p.buttons.filter(b => normalize(b.remote_name || b.name) === normalize(name)
          && b.code_in_local_store !== true && !b.verified);
        const match = matches.length === 1 && !used.has(matches[0].id) ? matches[0] : null;
        if (match) used.add(match.id);
        const opts = ['<option value="">Не импортировать</option>']
          .concat(p.buttons.map(b => `<option value="${h(b.id)}" ${match?.id === b.id ? 'selected' : ''}>
            ${h(b.name)}${b.code_in_local_store === true || b.verified ? ' · уже обучена' : ''}</option>`))
          .join('');
        return `<label class="form-field"><span><b data-no-translate>${h(name)}</b> → кнопка IR Studio</span>
          <select data-ir-binding-source="${h(name)}">${opts}</select></label>`;
      }).join('');
      this._dialog(`<h3>Сопоставление ИК-кодов · ${h(p.name)}</h3>
        <p>Найдено настоящих сигналов: <b>${available.length}</b>; неподдерживаемых форматов: <b>${unsupported.length}</b>.
        Совпавшие имена подставлены автоматически; для остальных выбери нужную кнопку.</p>
        <p class="muted tiny">Устройство должно соответствовать выбранному .ir профилю.
        Передача не начинается при импорте — сначала проверь одну кнопку.</p>
        <div class="form-stack" style="max-height:55vh;overflow:auto">${rows}</div>
        <div class="dialog-footer">
          <button data-action="ir-file-open">Другой файл</button>
          <button class="primary" data-action="ir-file-commit">Сохранить выбранные коды</button>
        </div>`);
    } catch (error) {
      this._irFileContent = null;
      this._toast('Ошибка чтения ИК-файла: ' + (error.message || error), true);
    }
  }

  async _importIrFileCodes() {
    const profile = this._selected();
    if (!profile || profile.id !== this._irFileProfile || !this._irFileContent) return;
    const selections = [...this.shadowRoot.querySelectorAll('[data-ir-binding-source]')];
    const mappings = selections.filter(input => input.value).map(input => ({
      source_name:input.dataset.irBindingSource, button_id:input.value,
    }));
    if (!mappings.length) {
      this._toast('Выбери минимум одну кнопку для сохранения', true);
      return;
    }
    if (new Set(mappings.map(x => x.button_id)).size !== mappings.length) {
      this._toast('Каждой кнопке соответствует только один исходный ИК-код', true);
      return;
    }
    try {
      const result = await this._call('ir_file_import', {
        profile_id:profile.id,content:this._irFileContent,mappings,
      });
      this._irFileContent = null;
      this._dialogClose();
      await this._load();
      this._render();
      this._toast(`ИК-кодов сохранено: ${result.codes_imported}; уже обученных не затронуто: ${result.existing_preserved}. Проверь отправку на устройстве.`);
    } catch (error) {
      this._toast('Не удалось сохранить ИК-коды: ' + (error.message || String(error)), true);
    }
  }

  _showImportModal(btnId) {
    const p=this._selected(),b=p?.buttons.find(b=>b.id===btnId);if(!b)return;
    const native = p.source === 'ir_studio';
    const legacy = p.source === 'tuya_ir';
    if (p.source === 'tuya_local') {
      this._showNotice('Tuya Local хранит DP202-коды в собственном хранилище. Обучай и отправляй команды через IR Studio; для сохранения кодов включай полную резервную копию Home Assistant.');
      return;
    }
    if (!native && !legacy) {
      this._showNotice('Этот Remote не поддерживает прямую отправку импортированного кода. Для него используй публичное remote.learn_command.');
      return;
    }
    const format = native ? 'tuya_dp202' : 'raw_ir';
    const formatLabel = native ? 'Tuya DP202 — исходная строка' : 'RAW Base64 — u16LE';
    const placeholder = native ? 'DP202 payload' : 'Base64 ИК-посылки';
    const description = native
      ? 'Вставь исходную строку DP202 из совместимого бэкапа. Не перекодируй её в Base64.'
      : 'Вставь Base64 с RAW u16LE длительностями ИК-сигнала. Код останется только в IR Studio и не обучит внешний Remote.';
    this._dialog(`<h3>Импорт ИК-кода: ${h(p.name)} / ${h(b.name)}</h3>
      <label>Формат сигнала</label>
      <select id="raw-format"><option value="${format}">${formatLabel}</option></select>
      <p class="muted">${description}</p>
      <textarea id="raw-code" rows="5" placeholder="${placeholder}"></textarea>
      <p class="tiny">${native ? 'Импорт не доказывает физическую отправку.' : 'RAW сохраняется только в IR Studio. Для отправки внешним Remote обучи его через remote.learn_command.'}</p>
      <div class="dialog-footer"><button data-action="close-modal">Отмена</button><button class="primary" data-action="import-raw" data-button="${h(b.id)}">Сохранить код</button></div>`);
  }

  async _start(kind, btnId) {
    const profile = this._selected();
    if (!profile || (kind === 'learn' && this._pending)) return false;
    // A sequential session must not learn a signal into the wrong button.
    if (kind === 'learn' && this._learnWizard &&
        (this._learnWizard.profileId !== profile.id ||
         this._learnWizard.buttonIds[this._learnWizard.index] !== btnId)) {
      this._toast('Используй кнопку «Продолжить обучение» в мастере', true);
      return false;
    }
    try {
      // Native IR Studio supports a 60-second learn window. Other remote
      // drivers may finish earlier (Tuya Local has a 30-second internal limit).
      const timeout = 60;
      const result = await this._call('start', {
        kind, profile_id: profile.id, button_id: btnId, timeout,
      });
      if (!result?.job_id) throw new Error('Не получен идентификатор задания');
      this._pending = {
        id: result.job_id, kind, buttonId: btnId, profileId: profile.id,
        started: Date.now(), timeout, cancelling: false,
      };
      if (this._learnWizard) this._render();
      else this._renderRows();
      this._startJobPolling();
      await this._poll();
      return true;
    } catch (error) {
      this._toast('Не удалось начать операцию: ' + (error.message || String(error)), true);
      return false;
    }
  }

  _startJobPolling() {
    if (this._poller) clearInterval(this._poller);
    this._lastPollAt = 0;
    this._poller = setInterval(() => {
      this._updateLearningCountdown();
      void this._poll();
    }, 250);
    this._updateLearningCountdown();
  }

  _updateLearningCountdown() {
    const pending = this._pending;
    if (!pending || pending.kind !== 'learn') return;
    const clock = this.shadowRoot.querySelector('.learn-clock');
    const seconds = this.shadowRoot.querySelector('.learn-seconds');
    if (!clock || !seconds) return;
    const remaining = Math.max(0, Math.ceil(
      (pending.started + pending.timeout * 1000 - Date.now()) / 1000
    ));
    seconds.textContent = pending.cancelling ? '×' : String(remaining);
    clock.style.setProperty('--progress', (remaining / pending.timeout * 100) + '%');
  }

  async _cancelLearning() {
    const pending = this._pending;
    if (!pending || pending.kind !== 'learn' || pending.cancelling) return;
    pending.cancelling = true;
    this._renderRows();
    this._updateLearningCountdown();
    try {
      await this._call('job_cancel', {job_id: pending.id});
      // Poll immediately after an explicit cancellation; rate limiting here
      // could leave a stale pending job that blocks the next learning attempt.
      this._lastPollAt = 0;
      await this._poll();
    } catch (error) {
      if (this._pending === pending) {
        pending.cancelling = false;
        this._renderRows();
      }
      this._toast('Не удалось отменить обучение: ' + (error.message || String(error)), true);
    }
  }

  async _poll() {
    const pending = this._pending;
    if (!pending?.id || this._pollBusy) return;
    if (Date.now() - (this._lastPollAt || 0) < 850) return;
    this._lastPollAt = Date.now();
    this._pollBusy = true;
    try {
      const job = await this._call('job', {job_id: pending.id});
      if (this._pending !== pending) return;
      if (job.status === 'running' || job.status === 'cancelling') {
        pending.cancelling = job.status === 'cancelling' || pending.cancelling;
        this._updateLearningCountdown();
        return;
      }
      if (this._poller) clearInterval(this._poller);
      this._poller = null;
      this._pending = null;
      await this._load();
      const wizard = this._learnWizard;
      if (wizard && pending.kind === 'learn' &&
          wizard.profileId === pending.profileId &&
          wizard.buttonIds[wizard.index] === pending.buttonId) {
        if (job.status === 'done') {
          wizard.completed++;
          wizard.index++;
          wizard.lastResult = 'ИК-сигнал получен и сохранён.';
        } else {
          wizard.lastResult = job.status === 'cancelled'
            ? 'Приём отменён. Повтори или пропусти эту кнопку.'
            : 'Сигнал не получен. Повтори или пропусти эту кнопку.';
        }
        this._render();
      }
      const message = job.status === 'cancelled'
        ? 'Приём сигнала отменён'
        : job.status === 'done'
          ? job.kind === 'learn'
            ? 'ИК-сигнал получен и сохранён'
            : 'Команда отправлена (физическая реакция не проверялась)'
          : job.message || 'Операция не выполнена';
      this._toast(message, job.status === 'failed');
    } catch (error) {
      // Temporary WebSocket failure must NOT lose the cancellable job handle.
      // Keep polling; a fresh page load can also recover the active job.
      if (this._pending === pending) this._updateLearningCountdown();
    } finally {
      this._pollBusy = false;
    }
  }

  _showNotice(message) {
    this._dialog(`<h3>Сообщение</h3><div class="banner">${h(message)}</div><div class="dialog-footer"><button data-action="close-modal">Закрыть</button></div>`);
  }

  async _doChange(type, extra) {
    try { const response=await this._call(type,extra); await this._load(); return response; }
    catch(e) {this._showNotice('Ошибка: '+(e.message||e));return null;}
  }


  _toast(message, bad=false) {
    const old = this.shadowRoot.querySelector('#studio-toast');
    if (old) old.remove();
    const toast=document.createElement('div');
    toast.id='studio-toast'; toast.className='toast';
    toast.style.borderLeft='3px solid '+(bad?'#ef4444':'#0891b2');
    toast.textContent=this._translateText(message);
    this.shadowRoot.appendChild(toast);
    setTimeout(()=>{if(toast.isConnected)toast.remove();}, 6500);
  }

  _downloadJson(filename, data) {
    const blob = new Blob([JSON.stringify(data, null, 2) + '\n'], {type: 'application/json;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = filename; link.style.display = 'none';
    this.shadowRoot.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  _openBackup() {
    this._importBackup=null;
    this._dialog(`<h3>Резервная копия пультов</h3>
      <p class="muted tiny">Выбери нужные пульты. Импорт не удаляет остальные пульты и не меняет их без выбранного режима замены.</p>
      <div class="row" style="margin:10px 0"><button data-action="backup-mode-export" class="primary">Экспорт</button><button data-action="backup-mode-import">Импорт</button></div>
      <div id="backup-content"></div>
      <div class="dialog-footer"><button data-action="close-modal">Закрыть</button></div>`);
    this._renderBackupExport();
  }

  _backupRows(profiles) {
    if (!profiles.length) return '<p class="muted">Нет пультов</p>';
    return `<div class="row" style="gap:8px;margin:8px 0"><button data-action="backup-select-all">Выбрать все</button><button data-action="backup-select-none">Снять выбор</button></div>` +
      profiles.map(p => `<label class="backup-row"><input type="checkbox" data-backup-choice="${h(p.id)}" checked />
      <span><b data-no-translate>${h(p.name)}</b> <small>· ${p.buttons?.length || 0} команд</small></span></label>`).join('');
  }

  _backupImportRows(profiles) {
    if (!profiles.length) return '<p class="muted">Нет пультов в резервной копии</p>';
    // Bind each restored appliance to a *current* HA Remote executor. Old
    // entity IDs in backup files can be stale after reinstalling the gateway.
    const remotes = this._remotes().filter(r=>['on','off'].includes(r.status));
    const soleRemote = remotes.length === 1 ? remotes[0] : null;
    return `<div class="row" style="gap:8px;margin:8px 0"><button data-action="backup-select-all">Выбрать все</button><button data-action="backup-select-none">Снять выбор</button></div>` +
      profiles.map(p => {
        // One available physical transmitter is unambiguous, even when the
        // backup points to an old entity. Do not require a redundant click.
        const selected = soleRemote?.id || (remotes.some(r=>r.id===p.remote_entity)
          ? p.remote_entity : '');
        const binding = soleRemote
          ? `<input type="hidden" data-backup-remote="${h(p.id)}" value="${h(soleRemote.id)}" />
             <p class="tiny">ИК-исполнитель: <b data-no-translate>${h(soleRemote.name)}</b>
               <span class="muted">· ${h(soleRemote.id)} · выбран автоматически</span></p>`
          : `<label class="tiny" for="backup-remote-${h(p.id)}">ИК-устройство для отправки команд</label>
             <select id="backup-remote-${h(p.id)}" data-backup-remote="${h(p.id)}">
               <option value="" ${!selected?'selected':''} disabled>${remotes.length ? 'Выберите действующий ИК-шлюз' : 'Нет доступных ИК-шлюзов'}</option>
               ${remotes.map(r=>`<option value="${h(r.id)}" ${r.id===selected?'selected':''}>${h(r.name)} · ${h(r.id)}</option>`).join('')}
             </select>`;
        return `<div class="backup-row" style="display:block">
          <label><input type="checkbox" data-backup-choice="${h(p.id)}" checked />
            <b data-no-translate>${h(p.name)}</b>
            <small>· ${p.buttons?.length||0} команд</small></label>
          ${binding}
          <small class="muted">В резервной копии: ${h(p.remote_entity||'не указан')}</small>
        </div>`;
      }).join('');
  }

  _selectedBackupIds() {
    return [...this.shadowRoot.querySelectorAll('[data-backup-choice]:checked')].map(el=>el.dataset.backupChoice);
  }

  _renderBackupExport() {
    const host=this.shadowRoot.querySelector('#backup-content');if(!host)return;
    this._setHTML(host, `<h3>Экспорт</h3>${this._backupRows(this._data.profiles)}
      <p class="tiny muted">Сырые ИК-сигналы включаются, только если они доступны в локальном хранилище IR Studio или поддерживаемого драйвера. Секретные ключи не экспортируются.</p>
      <button class="primary" data-action="backup-export">Скачать выбранные пульты</button>`);
  }

  _renderBackupImport() {
    const host=this.shadowRoot.querySelector('#backup-content');if(!host)return;
    const data=this._importBackup;
    this._setHTML(host, `<h3>Импорт</h3><label>Файл резервной копии JSON</label>
      <input type="file" id="backup-file" accept=".json,application/json" />
      <div id="backup-import-list">${data ? this._backupImportRows(data.profiles || []) : '<p class="tiny muted">Сначала выбери JSON-файл.</p>'}</div>
      <p class="tiny muted">Если доступен один физический ИК-шлюз Home Assistant, он выбирается автоматически. Если их несколько — выбери исполнителя для каждого пульта. Коды и внутренние имена команд не изменяются.</p>
      <label>Если пульт уже существует</label>
      <select id="backup-strategy"><option value="skip">Пропустить существующие (безопасно)</option>
        <option value="merge">Добавить отсутствующие кнопки</option>
        <option value="replace">Заменить выбранные пульты</option></select>
      <p class="tiny muted">Импортированные сигналы сохраняются в отдельном хранилище. Коды Tuya DP202 можно отправлять через нативный хаб ИК Студии после его привязки; преобразование в форматы сторонних драйверов не выполняется.</p>
      <button class="primary" data-action="backup-import" ${data?'':'disabled'}>Импортировать выбранные пульты</button>`);
    host.querySelector('#backup-file').onchange=async(e)=>{
      const file=e.target.files?.[0];if(!file)return;
      if(file.size>5*1024*1024){this._toast('Файл слишком большой (максимум 5 МБ)',true);return;}
      try {
        const backup=JSON.parse(await file.text());
        const arr=backup.format==='ir-studio-profile' && backup.format_version===1 ? [backup.profile] : backup.profiles;
        if(!Array.isArray(arr)||!['tuya-ir-studio-backup','ir-studio-backup','ir-studio-profile'].includes(backup.format))
          throw new Error('Формат файла не поддерживается');
        this._importBackup={...backup,profiles:arr};
        this._renderBackupImport();
      } catch(err){this._toast('Не удалось прочитать JSON: '+(err.message||err),true);}
    };
  }

  async _backupExport() {
    const profile_ids=this._selectedBackupIds();
    if(!profile_ids.length){this._toast('Выбери хотя бы один пульт',true);return;}
    try {
      const payload=await this._call('backup_export',{profile_ids});
      const date=new Date().toISOString().slice(0,10);
      this._downloadJson(`tuya_ir_studio_backup_${date}.json`,payload);
      this._dialogClose();
      this._toast(`Экспортировано ${payload.profiles.length} пультов · RAW-кодов ${payload.raw_ir_codes_included}.`);
    } catch(err){this._toast('Ошибка экспорта: '+(err.message||err),true);}
  }

  async _backupImport() {
    const profile_ids=this._selectedBackupIds();
    if(!this._importBackup||!profile_ids.length){this._toast('Выбери файл и хотя бы один пульт',true);return;}
    const strategy=this.shadowRoot.querySelector('#backup-strategy')?.value||'skip';
    const backup=this._importBackup;
    const remote_bindings={};
    const choices=[...this.shadowRoot.querySelectorAll('[data-backup-remote]')];
    for (const profile_id of profile_ids) {
      const choice=choices.find(el=>el.dataset.backupRemote===profile_id);
      if (!choice?.value) {
        this._toast('Выбери ИК-устройство для каждого импортируемого пульта',true);
        return;
      }
      remote_bindings[profile_id]=choice.value;
    }
    try {
      const args={backup,profile_ids,strategy,remote_bindings};
      const preview=await this._call('backup_import',{...args,dry_run:true});
      const ch=preview.changes;
      if(strategy==='replace' && ch.replaced_profiles.length &&
        !window.confirm(`Заменить ${ch.replaced_profiles.length} пульт(ов)? Старые профили будут заменены, но исходные RAW-коды внешнего драйвера не удаляются.`))return;
      const result=await this._call('backup_import',{...args,dry_run:false});
      this._importBackup=null;
      await this._load();this._dialogClose();
      const summary=result.changes;
      this._toast(`Импорт: новых ${summary.added_profiles.length}, объединено ${summary.merged_profiles.length}, заменено ${summary.replaced_profiles.length}, пропущено ${summary.skipped_profiles.length}.`);
    } catch(err){this._toast('Ошибка импорта: '+(err.message||err),true);}
  }

  _dragPointerDown(event) {
    const handle = event.target.closest?.('[data-profile-drag],[data-drag-handle]');
    if (!handle || (event.pointerType === 'mouse' && event.button !== 0)) return;
    const isProfile = handle.hasAttribute('data-profile-drag');
    const row = handle.closest(isProfile?'[data-profile-row]':'[data-button-row]');
    if (!row) return;
    event.preventDefault();
    handle.setPointerCapture?.(event.pointerId);
    const id = isProfile ? row.dataset.profileRow : row.dataset.buttonRow;
    this._drag = {
      kind:isProfile?'profile':'button', pointerId:event.pointerId,
      sourceId:id, targetId:id, position:'before',
      startY:event.clientY, moved:false,
    };
    row.classList.add('dragging');
  }

  _dragPointerMove(event) {
    const drag = this._drag;
    if (!drag || event.pointerId !== drag.pointerId) return;
    if (Math.abs(event.clientY - drag.startY) > 4) drag.moved = true;
    if (!drag.moved) return;
    const selector = drag.kind==='profile'?'[data-profile-row]':'[data-button-row]';
    const rows = [...this.shadowRoot.querySelectorAll(selector)];
    let target = null, nearest = Infinity;
    for (const row of rows) {
      const rect = row.getBoundingClientRect();
      const distance = event.clientY < rect.top ? rect.top-event.clientY
        : event.clientY > rect.bottom ? event.clientY-rect.bottom : 0;
      if (distance < nearest) {nearest=distance;target=row;}
      if (distance===0) break;
    }
    if (!target) return;
    const rect=target.getBoundingClientRect();
    drag.targetId=drag.kind==='profile'?target.dataset.profileRow:target.dataset.buttonRow;
    drag.position=event.clientY>rect.top+rect.height/2?'after':'before';
    for (const row of rows) {
      row.classList.remove('drop-before','drop-after');
      if (row===target) row.classList.add(drag.position==='before'?'drop-before':'drop-after');
    }
  }

  async _dragPointerUp(event) {
    const drag = this._drag;
    if (!drag || event.pointerId !== drag.pointerId) return;
    this._clearDrag();
    if (!drag.moved || !drag.targetId || drag.targetId===drag.sourceId) return;
    if (drag.kind==='profile') {
      await this._doChange('profile_reorder', {
        profile_id:drag.sourceId, target_profile_id:drag.targetId,
        position:drag.position,
      });
      return;
    }
    const profile=this._selected();
    if (!profile) return;
    await this._doChange('button_reorder', {
      profile_id:profile.id,button_id:drag.sourceId,
      target_button_id:drag.targetId,position:drag.position,
    });
  }

  _clearDrag() {
    this._drag=null;
    for (const row of this.shadowRoot.querySelectorAll('[data-button-row],[data-profile-row]')) {
      row.classList.remove('dragging','drop-before','drop-after');
    }
  }

  async _handleProfileDragKeydown(event) {
    const handle=event.target.closest?.('[data-profile-drag]');
    if (!handle || !['ArrowUp','ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    await this._moveProfile(handle.dataset.profileDrag, event.key==='ArrowUp'?'up':'down');
  }

  async _moveProfile(profileId, direction) {
    const profiles=this._data?.profiles || [];
    const index=profiles.findIndex(p=>p.id===profileId);
    const delta=direction==='up'?-1:direction==='down'?1:0;
    const next=index+delta;
    if (index<0 || !delta || next<0 || next>=profiles.length) return false;
    const result=await this._doChange('profile_reorder', {
      profile_id:profileId,target_profile_id:profiles[next].id,
      position:delta<0?'before':'after',
    });
    if (result?.moved) {
      const handles=this.shadowRoot.querySelectorAll('[data-profile-drag]');
      [...handles].find(el=>el.dataset.profileDrag===profileId)?.focus?.();
    }
    return Boolean(result?.moved);
  }

  async _addCommandFromInput() {
    const profile = this._selected();
    const input = this.shadowRoot.querySelector('#new-button');
    const name = input?.value?.trim();
    if (!profile || !name || this._commandAddBusy) return;
    this._commandAddBusy = true;
    try {
      const library = Object.entries(this._data?.template_catalog?.commands || {});
      const matched = library.find(([, entry]) =>
        entry?.labels?.en?.toLocaleLowerCase() === name.toLocaleLowerCase());
      if (matched) {
        await this._doChange('button_add_set', {
          profile_id: profile.id, set_ids: [], command_ids: [matched[0]],
          language: this._language(),
        });
      } else {
        await this._doChange('button_add', {profile_id: profile.id, name});
      }
    } finally {
      this._commandAddBusy = false;
    }
  }

  async _handleClick(event) {
    const btn=event.target.closest('[data-action]');if(!btn)return;
    const action=btn.dataset.action,bid=btn.dataset.button;
    const p=this._selected();
    if(action==='select'){
      // Do not hide an active receiver by switching to another remote.
      // First cancel/finish the current guide so the job remains accessible.
      if (btn.dataset.profile !== this._active &&
          (this._batchStarting || this._pending?.kind === 'learn')) {
        this._toast('Сначала заверши или отмени обучение текущего пульта', true);
        return;
      }
      if (this._learnWizard && this._learnWizard.profileId !== btn.dataset.profile)
        this._learnWizard = null;
      this._active=btn.dataset.profile;this._filter='';this._render();
    }
    else if(action==='refresh') await this._load();
    else if(action==='open-backup') this._openBackup();
    else if(action==='backup-mode-export') this._renderBackupExport();
    else if(action==='backup-mode-import') this._renderBackupImport();
    else if(action==='backup-select-all') this.shadowRoot.querySelectorAll('[data-backup-choice]').forEach(el=>el.checked=true);
    else if(action==='backup-select-none') this.shadowRoot.querySelectorAll('[data-backup-choice]').forEach(el=>el.checked=false);
    else if(action==='backup-export') await this._backupExport();
    else if(action==='backup-import') await this._backupImport();
    else if(action==='new-profile')this._showCreateProfile();
    else if(action==='profile-settings')this._showProfileSettings();
    else if(action==='choose-icon') {
      const icon=btn.dataset.iconChoice;
      const picker=btn.closest('.icon-picker');
      if (!ICON_BY_ID.has(icon) || !picker) return;
      const field=picker.querySelector('[data-selected-icon]');
      const preview=picker.querySelector('[data-icon-preview]');
      if (field) field.value=icon;
      if (preview) preview.innerHTML=deviceIcon(icon);
      const caption=picker.querySelector('[data-icon-picker-caption]');
      if (caption) {
        const item=ICON_BY_ID.get(icon),lang=this._language();
        caption.innerHTML=h(item?.labels?.[lang]||item?.labels?.en||icon) +
          '<small>Без изменения ИК-команд</small>';
      }
      this._updateCreateProfileValidity();
      picker.querySelectorAll('[data-icon-choice]').forEach(el =>
        el.setAttribute('aria-pressed',String(el.dataset.iconChoice===icon)));
      picker.querySelector('details').open=false;
    }
    else if(action==='review-unlearned')this._showReviewUnlearned();
    else if(action==='cleanup-all')this.shadowRoot.querySelectorAll('[data-cleanup-id]').forEach(el=>el.checked=true);
    else if(action==='cleanup-none')this.shadowRoot.querySelectorAll('[data-cleanup-id]').forEach(el=>el.checked=false);
    else if(action==='cleanup-selected')await this._cleanupSelected();
    else if(action==='save-profile-settings')await this._saveProfileSettings();
    else if(action==='button-library')this._showButtonLibrary();
    else if(action==='button-sets-select-all') this.shadowRoot.querySelectorAll('[data-set-choice]').forEach(el=>el.checked=true);
    else if(action==='button-sets-select-none') this.shadowRoot.querySelectorAll('[data-set-choice],[data-command-choice]').forEach(el=>el.checked=false);
    else if(action==='add-button-sets') {
      const set_ids=[...this.shadowRoot.querySelectorAll('[data-set-choice]:checked')].map(el=>el.dataset.setChoice);
      const command_ids=[...this.shadowRoot.querySelectorAll('[data-command-choice]:checked')].map(el=>el.dataset.commandChoice);
      const result=await this._doChange('button_add_set',{profile_id:p.id,set_ids,command_ids,language:this._language()});
      if(result){this._dialogClose();this._toast(`Добавлено команд: ${result.added}; пропущено повторов: ${result.skipped}.`);}
    }
    else if(action==='close-modal')this._dialogClose();
    else if(action==='create-profile') {
      if(!this._updateCreateProfileValidity()){
        this._toast('Заполни название, выбери иконку и ИК-шлюз',true);
        return;
      }
      const modal=this.shadowRoot.querySelector('#modal');
      const name=modal.querySelector('#profile-name').value.trim();
      const entity_id=modal.querySelector('#profile-remote').value;
      const icon=modal.querySelector('#create-icon').value;
      const args={name,entity_id,icon};
      const r=await this._doChange('profile_add',args);
      if(r)this._selectedSource=entity_id;
      if(r){this._active=r.id;this._filter='';this._render();}
    }
    else if(action==='bind') {
      const entity_id=this.shadowRoot.querySelector('#bind-remote')?.value;
      if(entity_id && entity_id!==p.remote_entity) await this._doChange('profile_bind',{profile_id:p.id,entity_id});
    }
    else if(action==='rename-profile') this._showRenameProfile();
    else if(action==='save-profile-name') {
      const name=this.shadowRoot.querySelector('#rename-profile-name')?.value?.trim();
      if(name){const r=await this._doChange('profile_rename',{profile_id:p.id,name});if(r)this._dialogClose();}
    }
    else if(action==='delete-profile') {
      if(window.confirm(`Удалить пульт «${p.name}», его кнопки и импортированные IR Studio коды? Сигналы, обученные в самом HA Remote, сохраняются.`))
        await this._doChange('profile_delete',{profile_id:p.id});
    }
    else if(action==='new-button') await this._addCommandFromInput();
    else if(action==='rename-button') this._showRenameButton(bid);
    else if(action==='save-button-name') {
      const name=this.shadowRoot.querySelector('#rename-button-name')?.value?.trim();
      if(name){const r=await this._doChange('button_rename',{profile_id:p.id,button_id:bid,name});if(r)this._dialogClose();}
    }
    else if(action==='move-button') await this._doChange('button_move',{profile_id:p.id,button_id:bid,direction:btn.dataset.direction});
    else if(action==='delete-button') {
      const b=p.buttons.find(x=>x.id===bid);
      if(window.confirm(`Удалить кнопку «${b?.name}» из ИК Студии?`))
        await this._doChange('button_delete',{profile_id:p.id,button_id:bid});
    }
    else if(action==='learn-all') await this._beginBatchLearning();
    else if(action==='learn-next') await this._batchLearnNext();
    else if(action==='learn-skip') this._batchLearnSkip();
    else if(action==='learn-finish') await this._batchLearnFinish();
    else if(action==='learn-modal') await this._start('learn',bid);
    else if(action==='cancel-job') await this._cancelLearning();
    else if(action==='send') await this._start('send',bid);
    else if(action==='ir-file-open') this._showIrFileImport();
    else if(action==='ir-file-pick') this.shadowRoot.querySelector('#ir-profile-file')?.click();
    else if(action==='ir-file-commit') await this._importIrFileCodes();
    else if(action==='import-modal') this._showImportModal(bid);
    else if(action==='import-raw') {
      const payload=this.shadowRoot.querySelector('#raw-code')?.value?.trim();
      const format=this.shadowRoot.querySelector('#raw-format')?.value||'raw_ir';
      const r=await this._doChange('import_raw',{profile_id:p.id,button_id:bid,payload,format});
      if(r)this._showNotice(r.sendable_via_bound_remote ? 'Код сохранён. Нажми «Послать», чтобы проверить его физически.' : 'RAW сохранён только в IR Studio. Код не загружен во внешний Remote; обучи его через remote.learn_command.');
    }
    else if(action==='verify') {
      const result=await this._doChange('verify',{job_id:btn.dataset.job});
      if(result)this._toast('Физическая реакция отмечена как проверенная.');
    }
  }
}

if (!customElements.get('ir-studio-panel')) customElements.define('ir-studio-panel', IRStudioPanel);
