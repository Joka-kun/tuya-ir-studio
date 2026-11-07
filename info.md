# Tuya IR Studio

Create, organize, learn and send **local infrared** remote commands with Home Assistant.

- Set up a compatible Tuya IR gateway by Smart Life/Tuya QR sign-in **for gateway credentials**, or manually by IP, Device ID and Local Key.
- Learn actual IR signals using the original physical remote, with a guided sequence for multiple buttons.
- Create a Home Assistant virtual device per remote and control learned keys with native `button.press` or `remote.send_command` actions.
- Use **Configure** in Devices & services to manage and learn commands, with an optional advanced sidebar for templates, compatible Flipper `.ir` files and local backups.
- Choose remote icons independently from device types; icons never change the IR payloads.
- Fully independent of Tuya Cloud for **sending already learned local commands** when the LAN and gateway are available.

**Not included:** Smart Life cloud button-list import, guessed IR codes or a cloned Smart Life remote layout. Device-type templates contain names only and never automatically become working infrared signals.

Compatibility requires a real IR receiver/transmitter; RF/Bluetooth/Wi-Fi/HDMI-CEC remotes are not directly learnable. Physical verification depends on the gateway firmware and protocol. For installation and limitations, see [README](README.md).
