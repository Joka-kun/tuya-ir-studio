# Importing an existing infrared code file (advanced)

This optional feature is **not necessary** for ordinary use. The recommended workflow is to **teach commands using your original physical infrared remote**.

IR Studio can preview a compatible Flipper `.ir` file and attach supported signals to buttons in a **local native IR Studio profile**.

## Safe workflow

1. In the IR Studio sidebar, open or create a remote bound to a native local IR hub.
2. In the remote settings, expand **Advanced → Load IR file**.
3. Choose an existing **Flipper .ir** file belonging to the **exact device model**. Matching only a device type (TV, light, projector) is insufficient.
4. Preview the contained names and explicitly map the desired signals to your local button names.
5. Save the selected codes, then **test actual physical transmission** against the device. Codes from a file are not marked physically verified merely because saving succeeds.

## Formats and limits

The importer currently recognizes supported Flipper IR records such as `raw`, `NEC` and `NECext` when they meet the integration's parser/transport constraints. Other protocols, radio-frequency formats or malformed files can be rejected. Nothing is downloaded from Tuya or other sites on your behalf.

- Never overwrite previously learned commands without reviewing the operation.
- Existing verified local signals must remain intact on import errors and storage failures.
- Importing names without waveform data **does not** create a working IR button.
- Local IR transmission may depend on the gateway protocol and firmware.
- Do not include Local Keys, OAuth tokens or real private device identifiers in shared files and issues.

[Main README](../README.md) · [Русская версия](../README_RU.md) · [Roadmap](../ROADMAP.md)
