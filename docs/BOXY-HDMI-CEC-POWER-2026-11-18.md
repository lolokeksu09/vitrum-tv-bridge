# BOXY HDMI-CEC power synchronization — 2026-11-18

Device: SkyworthDigital HP44H, BOXY Android TV 11, the owner's private LAN ADB endpoint.
Owner reports that TV and BOXY power down together and requests independent TV power.

## Verified UI before change
Historic TV screenshot removed from the public repository for privacy.
Path: **Настройки → Настройки устройства → Экран и звук → HDMI CEC**.
Values on BOXY:
- `CEC переключатель`: ON (preserved).
- `Контроль громкости`: OFF (preserved).
- `Воспроизведение одной кнопкой`: OFF (preserved).
- `Автоматическое отключение устройства`: ON.

## Change performed
Through the authorized private GitHub/Termux ADB bridge, pressed OK on the
confirmed `Автоматическое отключение устройства` row (issue #410).
The previous private test recorded that the setting was **OFF**; the historical screenshot was removed for privacy.

No package was disabled; no HDMI-CEC master toggle, DNS, launcher, firmware,
system audio or TV power command was changed. This UI setting can decouple
one direction of HDMI-CEC standby behavior.

**Not yet established**: whether power-off behavior is fully decoupled on the
physical TV. Android TV and HDMI vendors implement CEC and remote IR power
settings differently. The firmware may still send standby from the BOXY,
and the remote's separately programmed TV-power button may also switch
both devices. We must not claim the original symptom is resolved until
the physical TV/BOXY power behavior is tested.

## Rollback
On the BOXY go to
`Настройки → Настройки устройства → Экран и звук → HDMI CEC`
and set **Автоматическое отключение устройства** back to ON.
This restores the pre-change setting. Screenshot before: `issue-405.png`;
after: `issue-411.png`.

## Follow-up only if synchronized power persists
Inspect the Android TV option
`Настройки → Настроить дистанционные кнопки → Питание`,
and any TV-side HDMI-CEC/standby settings. Check the physical wiring,
including whether TV USB supplies the BOXY power. Do not disable HDMI-CEC
globally without confirming the effect on remote control and HDMI inputs.
