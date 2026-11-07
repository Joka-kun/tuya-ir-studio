# Changelog

## 1.0.2 — Safe completion of in-flight IR learning

- If Finish is pressed while a sequential-learning start is awaiting its WebSocket response, queue cancellation and stop that exact job as soon as its ID arrives.
- Prevent switching to a different remote during an active or starting IR learning session, keeping the cancellation control accessible.
- Protect Skip during start/stop transitions and cover delayed start, navigation and cancellation in regression tests.
- Preserve profile/button identifiers, command keys, learned IR waveforms and the 164-command library unchanged.

## 1.0.1 — Guided learning, input suggestions and command library

- Start IR sequential learning with the first click, show an explicit launch state and prevent overlapping starts. Force immediate status reconciliation after cancellation.
- Apply a common uppercase, compact caption style to all library commands. Existing stored IR waveforms, immutable remote keys and user-defined captions are preserved.
- Add 45 command names for RGB/LED lighting, TV and HDMI sources, projector optical controls and audio. New names remain unlearned until trained with a physical remote.
- Add command-name suggestions and Enter-to-add in the sidebar; selected library suggestions keep canonical command keys. Include search in grouped library cards.
- Automated regression and HACS/Hassfest checks; real hardware IR learning and transmission require acceptance testing.

## 1.0.0 — Initial public release

- Local-first Tuya infrared gateway onboarding using QR-assisted sign-in or manual LAN credentials.
- Virtual Home Assistant remotes and learned button entities, with optional advanced sidebar.
- Persistent local IR profiles, backup and supported IR file imports without invented waveforms.
- Remote ordering using one drag handle (mouse, touch or keyboard), retaining profile and entity identities.
- Automated Python and JavaScript tests, Hassfest and HACS Validation. Physical device compatibility must be validated separately.
