<p align="center"><img src="assets/banner.svg" alt="Tuya IR Studio — Local infrared control for Home Assistant" width="100%"></p>

<p align="center"><a href="README.md">English</a> &nbsp;·&nbsp; <a href="README_RU.md">Русский</a> &nbsp;·&nbsp; <a href="README_DE.md">Deutsch</a> &nbsp;·&nbsp; <a href="README_FR.md">Français</a> &nbsp;·&nbsp; <a href="README_ES.md">Español</a> &nbsp;·&nbsp; <a href="README_ZH.md">中文</a></p>

<p align="center">
  <a href="https://github.com/Joka-kun/tuya-ir-studio/actions/workflows/tests.yaml"><img src="https://github.com/Joka-kun/tuya-ir-studio/actions/workflows/tests.yaml/badge.svg" alt="Unit tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Joka-kun/tuya-ir-studio" alt="MIT"></a>
  <a href="https://hacs.xyz/"><img src="https://img.shields.io/badge/HACS-custom%20repository-18a4cb" alt="HACS custom repository"></a>
</p>

# Tuya IR Studio

A **local-first infrared remote manager** for Home Assistant. Connect a compatible Tuya IR hub, organize virtual remotes, learn commands with the original handset, and send them over your LAN.

**Scope:** speculative Smart Life cloud button imports have been removed. Tuya / Smart Life QR authentication is **only for onboarding the physical hub**; it does not import buttons, cloud presets or IR waveforms.

<p align="center"><img src="assets/workflow.svg" alt="Connect hub — create remote — learn buttons — control over LAN" width="100%"></p>

## What it does

| Feature | Behavior |
| --- | --- |
| Hub setup | Reuse IR Studio's own saved QR session, scan QR, or enter local connection credentials manually |
| Remote management | Use the built-in Configure wizard to create a remote, learn commands, rename or delete them; the advanced sidebar is optional |
| Learning | Guided step-by-step IR capture using the original physical remote |
| Home Assistant devices | Each profile creates a virtual device with its own `remote` entity; learned commands are exposed as native `button` entities for automations |
| Optional expert tools | Import compatible Flipper `.ir` files and create portable backups |
| Storage | Keep your profiles and learned signals in Home Assistant; no cloud required for sending |

## Installation

In **HACS → Search**, find **Tuya IR Studio**, install it, and restart Home Assistant if prompted. The integration is included in the official HACS catalog. If your HACS catalog has not refreshed yet, open **Custom repositories**, add `https://github.com/Joka-kun/tuya-ir-studio` as an **Integration**, and install it. Go to **Settings → Devices & services → Add integration → Tuya IR Studio**. Set up your local IR hub with QR-assisted Tuya sign-in or the manual IP / Device ID / Local Key path.

Open **Settings → Devices & services → Tuya IR Studio → Configure** to add a remote and learn its buttons through Home Assistant's built-in wizard. The advanced IR Studio sidebar is optional (hidden on new installs). Once a command is learned, use its native **button** or virtual **remote** entity in automations. A successful service call does not prove physical operation.

## Compatibility and limits

- Native LAN support targets compatible Tuya infrared gateways (including YRC11-type hardware); exact behavior depends on firmware, protocol version and the gateway's learning/transmit capabilities.
- Requires a real **infrared** transmitter/receiver. RF, Bluetooth, Wi-Fi, and HDMI-CEC commands cannot be learned as IR.
- Air conditioners sometimes use whole-state frames; independent button learning may not reproduce every state.
- QR is for discovering/configuring a gateway, **not** for downloading Smart Life remote key layouts or codes. No buttons are synthesized from a device category.
- Local learned commands can work without Internet once the hub is configured, provided the driver and LAN remain available. QR onboarding may require Tuya connectivity.

## Documentation

[Native Configure workflow](docs/NATIVE_CONFIGURE.md) · [Home Assistant devices and entities](docs/HA_ENTITY_MODEL.md) · [Getting started](docs/TUYA_ONBOARDING.md) · [Offline .ir code import](docs/OFFLINE_IR_CODE_FILE_IMPORT.md) · [Roadmap](ROADMAP.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

Questions and bug reports: [GitHub Issues](https://github.com/Joka-kun/tuya-ir-studio/issues). Please include the Home Assistant version, gateway family, protocol and reproducible steps **without** Local Keys, tokens or personal identifiers.

MIT License · Independent open-source project, not affiliated with Tuya or Home Assistant.
