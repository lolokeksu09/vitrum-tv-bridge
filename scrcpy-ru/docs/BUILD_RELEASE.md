# BUILD & RELEASE — проверяемая цепочка поставки

Состояние на 2026-11-14. Текущий автоматизированный билд находится в `.github/workflows/build-scrcpy-ru.yml` ветки `build/scrcpy-ru-20261114` репозитория `lolokeksu09/vitrum-tv-bridge`.

## Что реально делает CI

1. Checkout локализации.
2. Клонирует `sw3gmach1n3/Scrcpy_for_Android` и переключает **точный** commit `d4a9a8caaaf8f0ff21ca6e3a3a406224b9116dd3`.
3. `python3 scrcpy-ru/apply_to_source.py android_source` (assert ожидаемых upstream фрагментов).
4. Валидирует 336 названий строк в трёх языках, устанавливает имя «Scrcpy RU», меняет `applicationId` на `ro.sw3g.scrcpy.ru`.
5. Устанавливает JDK 17, Android Platform 35 / build-tools 35, выполняет Gradle `assembleDebug`.
6. Проверяет существование APK, выводит `aapt dump badging` и SHA-256, публикует `Scrcpy-RU-APK` как Actions artifact.

**Подтверждение:** run `43509360631` завершился успешно. Его результат доказывает сборку, но не работу на Android TV или телефоне.

## Локальная воспроизводимость

При наличии git, Python 3, Java 17, Android SDK 35, Android Build Tools 35 и сети:

```bash
git clone https://github.com/sw3gmach1n3/Scrcpy_for_Android.git android_source
cd android_source
git checkout --detach d4a9a8caaaf8f0ff21ca6e3a3a406224b9116dd3
cd ..
python3 scrcpy-ru/apply_to_source.py android_source
cd android_source
./gradlew --no-daemon assembleDebug -Pandroid.injected.testOnly=false
```

Важное различие: локальная команда выше **не** выполняет CI-шаг переименования `applicationId` в `.ru` и имени приложения; для точного CI APK использовать workflow или повторить эти изменения отдельно. Нельзя устанавливать такой локальный APK поверх RU-пакета как идентичную сборку.

## Политика релизов

- Debug APK — для тестов. При выпуске `release`: отдельный стабильный ключ подписи, `apksigner verify`, версия/versionCode и provenance, checksums, changelog.
- Релизная подпись **не** хранится в репозитории и не публикуется в логах. Изменение подписанта может требовать отдельной установки и влияет на обновление с сохранением данных.
- После вывода в отдельный репозиторий перенести CI, сохранить upstream pin и воспроизводимость; не переносить старые captures и bridge utilities.
- CI workflow должен запускаться на изменениях исходников/локализации. Документационные изменения сами по себе не должны расходовать сборки после выделения проекта.
- Скриншоты UI, аудио, лог и реальные сетевые адреса не загружать в artifacts без отдельного согласия.

## Обновление до scrcpy 5.x

Отдельная feature branch с таблицей различий протокола (server/client handshake, codec metadata, control, audio, recording). Нельзя автоматически подменять `scrcpy-server` на новую версию в рамках рефакторинга профилей.
