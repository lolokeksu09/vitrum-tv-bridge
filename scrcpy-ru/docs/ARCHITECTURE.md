# ARCHITECTURE — границы изменений

Исходная кодовая база: `sw3gmach1n3/Scrcpy_for_Android` @ `d4a9a8caaaf8f0ff21ca6e3a3a406224b9116dd3`. Java, native Android UI, Android minSdk 26 / compileSdk 35 / targetSdk 35, Gradle 8.9, JDK 17 (по upstream build files).

## Подтверждённые узлы

| Узел | Сегодня | Предлагаемое действие |
| --- | --- | --- |
| `MainActivity.java` | Экран подключения, список всех опций, навигация, сохранение SharedPreferences, сессия, консоль | Декомпозировать экран профилей и сгруппированных настроек постепенно |
| `Options.java` | 35 полей, значения/валидация `server()`, SharedPreferences constructor | Добавить чтение из snapshot профиля, сохранить формат параметров сервера |
| `SettingsChoices.java` | Технические пресеты и выбор значений | Переиспользовать в новом редакторе |
| `ConnectionGate.java` | Разрешение попыток только в foreground и USB gating | Не менять контракт без регрессии |
| `Session.java` | ADB, запуск сервера, video/audio/control и запись | На этапе Profiles оставить стабильным |
| `RemoteView.java` | Касание, тачпад, зум, режимы | Добавить TV remote поверх существующего `Control`, не менять математику жестов |
| `I18n.java`, `HelpView.java` | App-owned language и справка | Новые UI строки в `values`, `values-ro`, `values-ru` |

## Целевые новые классы (ещё не созданы)

- `Profile.java`: immutable/value representation, validation-neutral.
- `ProfileValidator.java`: схема, диапазоны, допустимые значения, нормализация.
- `ProfileStore.java`: versioned atomic persistence, migration.
- `ProfilesScreen.java`: список, действия профиля, connect flow.
- `SettingsScreen.java`: групповое редактирование профиля, basic/advanced.
- `TvRemotePanel.java`: D-pad + Android keycodes через `Control.clickKey`.

Имена — ориентиры для новой реализации, а не свидетельство уже существующих файлов.

## Устойчивость и совместимость

- Транспорт и протокол scrcpy отделить от слоя хранения профилей.
- Не менять wire keys, server argument names, handshake или embedded `scrcpy-server` в этапах 1–3.
- Перед подключением валидировать `Options.server()` в snapshot без промежуточного изменения старых prefs.
- `Session` должен получить неизменяемые для сеанса параметры; UI может менять следующий snapshot, но не активный.
- Режим USB со многими устройствами требует явного выбора; пользовательский профиль не должен автоматически выдавать USB permission.
- До запуска любых фоновых recovery механизмов учитывать `ConnectionGate.canStart()` и ручное отключение.

## Технический долг (отдельно)

Встроенный scrcpy server 3.3.4 отстаёт от официального 5.0.1 по номеру версии. Нельзя просто заменить бинарник: протокол, сообщения, аудио и видео должны проходить совместимые тесты. Ротация log file и более информативное состояние соединения нужны независимо от версии сервера. AndroidX/Compose, cloud и фоновые службы не являются зависимостями Profiles v1.
