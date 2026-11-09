<p align="center"><img src="assets/banner.svg" alt="Tuya IR Studio — Local infrared control for Home Assistant" width="100%"></p>

<p align="center"><a href="README.md">English</a> &nbsp;·&nbsp; <a href="README_RU.md">Русский</a> &nbsp;·&nbsp; <a href="README_DE.md">Deutsch</a> &nbsp;·&nbsp; <a href="README_FR.md">Français</a> &nbsp;·&nbsp; <a href="README_ES.md">Español</a> &nbsp;·&nbsp; <a href="README_ZH.md">中文</a></p>

<p align="center">
  <a href="https://github.com/Joka-kun/tuya-ir-studio/actions/workflows/tests.yaml"><img src="https://img.shields.io/github/actions/workflow/status/Joka-kun/tuya-ir-studio/tests.yaml?branch=main&amp;label=tests&amp;style=flat-square" alt="Tests"></a>
  <a href="https://github.com/Joka-kun/tuya-ir-studio/releases"><img src="https://img.shields.io/github/v/release/Joka-kun/tuya-ir-studio?label=release&amp;style=flat-square" alt="Latest release"></a>
  <a href="https://www.home-assistant.io/integrations/marketplace/"><img src="https://img.shields.io/badge/Marketplace-listed-18A4CB?style=flat-square&amp;logo=homeassistant&amp;logoColor=white" alt="Marketplace listing"></a>
  <a href="docs/NATIVE_CONFIGURE.md"><img src="https://img.shields.io/badge/control-local%20IR-0F766E?style=flat-square" alt="Local IR"></a>
</p>

# Tuya IR Studio

A **community-maintained Home Assistant Marketplace integration** for local infrared remote control. Connect a compatible Tuya / Smart Life IR hub, organize virtual remotes, learn commands with the original handset, and transmit them over your LAN.

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

**Install:** In **Settings → Marketplace** (formerly **HACS**), search for **Tuya IR Studio** and install this community integration.

**Connect:** Go to **Settings → Devices & services → Add integration → Tuya IR Studio**. Set up your local IR hub with QR-assisted Tuya sign-in or the manual IP / Device ID / Local Key path.

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
