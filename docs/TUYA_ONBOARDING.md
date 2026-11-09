# Connecting a compatible Tuya IR hub

This guide covers **physical gateway onboarding**, not importing cloud buttons.

## Prerequisites

A compatible Tuya infrared gateway with a LAN address, a Home Assistant administrator account, and an original IR remote for learning. Optional QR onboarding needs Tuya/Smart Life account access. For manual setup, provide the hub's Device ID, Local Key and local host/IP.

## Setup

1. Install Tuya IR Studio in HACS, restart Home Assistant and go to **Settings → Devices & services → Add integration**.
2. Select **Tuya IR Studio**. Choose **Tuya/Smart Life QR**, **reuse IR Studio's own saved QR session**, or **manual local setup**.
3. For QR: enter the account's User Code, scan with Smart Life/Tuya, select the physical IR device and the correct parent gateway. A child `node_id` or `uuid` may be needed; the parent hub ID and child ID are not interchangeable.
4. Let IR Studio search your LAN for the configured gateway, or enter its reachable IP/hostname manually. Confirm the protocol and Local Key. If a hub is already configured, don't add the same hub again.
5. Open the IR Studio sidebar, create a **new remote**, add only the desired buttons and press **Learn in sequence**. Use the original infrared remote and verify the physical reaction to each learned command.
6. After learning, restart Home Assistant and try the same command again. For an offline test, disconnect the **Internet only**, not your LAN.

## Important distinctions

- QR does **not** import button names, Smart Life remote profiles, saved IR presets or code waveforms.
- Device type changes the **icon** but never generates a functional remote layout.
- A service acknowledgment or `remote.on` state is **not** physical proof of a successful IR send.
- Some protocols/firmware and complete-state AC remotes can behave differently.
- Do not expose Local Keys, user identifiers or token contents when asking for help.

For the Russian guide see [TUYA_ONBOARDING_RU.md](TUYA_ONBOARDING_RU.md). For advanced offline code import see [OFFLINE_IR_CODE_FILE_IMPORT.md](OFFLINE_IR_CODE_FILE_IMPORT.md).

## Session ownership

IR Studio only restores the session obtained by its own Tuya/Smart Life QR authorization, stored privately under `ir_studio_cloud_auth`. It never reads or refreshes a Tuya Local integration session. Existing Tuya Local credentials cannot be migrated; sign in once through IR Studio's own QR flow. External remote integrations are addressed only through Home Assistant's public `remote.*` services; imported RAW signals remain in IR Studio's own store and do not populate another integration's CodeStore.
