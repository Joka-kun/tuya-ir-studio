# Third-party notices

Tuya IR Studio is an independent integration distributed under the [MIT License](LICENSE). Third-party components remain subject to their own licenses.

## Direct Python dependencies

The requirements below are declared in [`manifest.json`](custom_components/ir_studio/manifest.json).

| Component | Requirement | License | Purpose |
| --- | --- | --- | --- |
| [TinyTuya](https://github.com/jasonacox/tinytuya) | `tinytuya==1.20.0` | MIT | Native Tuya LAN protocol framing, negotiation and TCP transport. |
| [Tuya Device Sharing SDK](https://github.com/tuya/tuya-device-sharing-sdk) | `tuya-device-sharing-sdk~=0.2.4` | MIT | Optional Tuya / Smart Life QR authorization and account-device metadata during onboarding. |
| [Segno](https://github.com/heuer/segno) | `segno==1.6.6` | BSD-3-Clause | QR code generation library. |

## Implementation reference

- **[make-all/tuya-local](https://github.com/make-all/tuya-local)** (MIT): its public onboarding flow, account-device mapping and LAN discovery behavior served as implementation references. Tuya Local is not a required runtime integration. IR Studio uses only its own authorized QR session and does not read or refresh Tuya Local's private authentication session. External remotes are addressed through Home Assistant's public `remote.*` services.

License information is available in the upstream repositories and Python package metadata: [TinyTuya](https://pypi.org/project/tinytuya/1.20.0/), [Tuya Device Sharing SDK](https://pypi.org/project/tuya-device-sharing-sdk/0.2.4/), and [Segno](https://pypi.org/project/segno/1.6.6/). This list documents direct requirements and implementation references, not every transitive dependency. The SDK requirement allows compatible versions rather than pinning an exact release; consult the license in the installed distribution for the actual version.
