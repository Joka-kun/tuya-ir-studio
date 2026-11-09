# Changelog

## 1.0.4 — Accurate counters after backup restoration

- Fix the sidebar's `0 of N learned` display after importing a backup with functional IR commands. A restored `needs_check` status now counts toward "learned/restored" while retaining a visible "needs verification" count.
- Do not mark imported commands as physically verified, inspect another integration's private CodeStore, alter the IR payload or force the user to re-learn a previously working command.
- The guided-learning wizard no longer treats opaque, imported `needs_check` entries as unlearned by default. If IR Studio itself knows a code is missing, learning remains available.
- Add an actual-panel JavaScript regression test with backed-up/foreign-store cases. No change to QR login or LAN transport.


## 1.0.3 — Isolation of third-party credentials and IR CodeStores

- Tuya/Smart Life QR login and token refresh now use only IR Studio's own private Home Assistant Store. Legacy unmarked credentials are purged, since older versions might have copied them from Tuya Local; a one-time fresh IR Studio QR login may be necessary. Subsequent explicitly marked IR Studio QR sessions survive restarts.
- Never read or mutate the Tuya IR integration's private CodeStore. Externally learned codes are handled through public `remote.learn_command` and `remote.send_command` services only; their storage cannot be asserted by IR Studio.
- Import RAW Base64 into IR Studio's independent local store for archive/backup only, without claiming it has been transmitted to an externally managed remote. Native Tuya DP202 imports remain separately supported.
- Add regression tests for foreign-runtime isolation, QR session provenance, RAW import/export, failure rollback and the unchanged native send paths.
- Automated tests and HACS/Hassfest checks are required before publishing the release. Physical learning and IR transmission are not certified by these checks.

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
