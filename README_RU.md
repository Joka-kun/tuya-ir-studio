<p align="center"><img src="assets/banner.svg" alt="Tuya IR Studio — локальные ИК-пульты в Home Assistant" width="100%"></p>

<p align="center"><a href="README.md">English</a> &nbsp;·&nbsp; <a href="README_RU.md">Русский</a> &nbsp;·&nbsp; <a href="README_DE.md">Deutsch</a> &nbsp;·&nbsp; <a href="README_FR.md">Français</a> &nbsp;·&nbsp; <a href="README_ES.md">Español</a> &nbsp;·&nbsp; <a href="README_ZH.md">中文</a></p>

<p align="center">
  <a href="https://github.com/Joka-kun/tuya-ir-studio/actions/workflows/tests.yaml"><img src="https://img.shields.io/github/actions/workflow/status/Joka-kun/tuya-ir-studio/tests.yaml?branch=main&amp;label=tests&amp;style=flat-square" alt="Тесты"></a>
  <a href="https://github.com/Joka-kun/tuya-ir-studio/releases"><img src="https://img.shields.io/github/v/release/Joka-kun/tuya-ir-studio?label=release&amp;style=flat-square" alt="Последний релиз"></a>
  <a href="https://www.home-assistant.io/integrations/marketplace/"><img src="https://img.shields.io/badge/Marketplace-listed-18A4CB?style=flat-square&amp;logo=homeassistant&amp;logoColor=white" alt="В каталоге Marketplace"></a>
  <a href="docs/NATIVE_CONFIGURE.md"><img src="https://img.shields.io/badge/control-local%20IR-0F766E?style=flat-square" alt="Локальный ИК"></a>
</p>

# Tuya IR Studio

**Tuya IR Studio — пользовательская интеграция из каталога Home Assistant Marketplace для локального ИК-управления.** Подключай совместимый ИК-шлюз Tuya / Smart Life, создавай пульты, обучай команды оригинальным физическим пультом и управляй по локальной сети.

**Что важно:** Экспериментальный импорт кнопок Smart Life удалён: он переносил технические названия без работающих ИК-сигналов. **QR теперь используется только для настройки шлюза**, а не для получения кнопок или готовых облачных кодов.

<p align="center"><img src="assets/workflow.svg" alt="Подключение шлюза — создание пульта — обучение — локальное управление" width="100%"></p>

## Возможности

| Функция | Что делает |
| --- | --- |
| Подключение шлюза | Вход через QR Smart Life / Tuya или ручной ввод IP, Device ID и Local Key |
| Управление пультами | Через стандартную кнопку «Настроить»: создание, обучение, переименование и удаление. Расширенная панель необязательна |
| Обучение | Пошаговое получение настоящего ИК-сигнала с оригинального пульта |
| Сущности Home Assistant | Для пульта создаётся устройство и сущность `remote`, для обученных команд — отдельные сущности `button` |
| Дополнительно | Импорт совместимых Flipper `.ir`-файлов и резервные копии |
| Хранение | Профили и ИК-сигналы остаются в Home Assistant; для отправки облако не требуется |

## Установка

**Установка:** открой **Настройки → Marketplace** (ранее **HACS**), найди **Tuya IR Studio** и установи интеграцию из каталога.

**Подключение:** открой **Настройки → Устройства и службы → Добавить интеграцию → Tuya IR Studio**. Подключи шлюз через QR или вручную.

Открой **Настройки → Устройства и службы → Tuya IR Studio → Настроить**. Здесь можно создать пульт, обучить кнопку, переименовать или удалить команды без отдельной боковой панели. На новых установках она скрыта и включается только по желанию. Для автоматизаций используй `button.press` или `remote.send_command`.

## Совместимость и ограничения

- Поддерживаются совместимые ИК-шлюзы Tuya, включая устройства семейства YRC11; реальные возможности зависят от прошивки, протокола и реализации приёма/передачи ИК.
- Нужен **инфракрасный** пульт. Bluetooth, RF, Wi-Fi и HDMI-CEC напрямую не обучаются.
- Кондиционеры могут отправлять полный пакет состояния, поэтому отдельная кнопка не всегда соответствует независимому коду.
- QR используется **только для подключения шлюза**. Названия, схемы и коды облачных пультов Smart Life автоматически не импортируются. Приложение ничего не подставляет по типу устройства.
- Обученные команды можно отправлять по LAN без Интернета, когда локальный шлюз доступен. Для первоначального QR-входа связь с Tuya может понадобиться.

## Документация

[Мастер «Настроить»](docs/NATIVE_CONFIGURE.md) · [Устройства и сущности Home Assistant](docs/HA_ENTITY_MODEL.md) · [Подключение шлюза](docs/TUYA_ONBOARDING_RU.md) · [Импорт готовых .ir-кодов](docs/OFFLINE_IR_CODE_FILE_IMPORT.md) · [План развития](ROADMAP.md) · [История изменений](CHANGELOG.md) · [Участие в разработке](CONTRIBUTING.md) · [Безопасность](SECURITY.md)

Ошибки и предложения: [GitHub Issues](https://github.com/Joka-kun/tuya-ir-studio/issues). Указывай модель шлюза, протокол, версию Home Assistant и шаги воспроизведения, **но не публикуй** Local Key, QR-токены и приватные идентификаторы.

MIT · Независимый проект, не связанный официально с Tuya или Home Assistant.
