# IR command library: naming and coverage

The Tuya IR Studio command library provides **English button captions**, not
a database of device-specific IR waveforms. A label such as `Power` or `Play`
does **not** prove a given appliance supports that command. Choose the names
actually present on the original remote, then learn the physical IR codes.

## Terminology

The names are informed by common remote-control interfaces:

- [Linux HDMI-CEC user-control command names](https://www.kernel.org/doc/html/latest/userspace-api/media/cec/cec-header.html): Select/OK, navigation, volume, mute, channel, play, pause, stop, input and power.
- [Android KeyEvent](https://developer.android.com/reference/android/view/KeyEvent): DPAD, Back, Home, media transport, volume and channel controls.

These are **semantic references only**. This project neither generates CEC
traffic nor treats these key names as an interoperable IR protocol.

## Catalog contract

- Every one of the 119 command IDs must appear in at least one command group.
- Every unique command ID has one immutable `key` (the learned-code identity).
- User-facing button labels are English and unique, with ASCII `+`/`-` for
  paired controls such as `VOL +` and `VOL -`.
- `Power` is normally a *toggle*; `Power On` and `Power Off` are separate
  discrete controls and must not be synthesized from `Power`.
- `Input` and `Source` remain distinct because real remotes may have both.
  Similarly `Previous` and `Last channel` are different actions.
- Climate controls may encode a whole device state in one IR frame; repeating
  `TEMP +` is **not** guaranteed to work on all appliances.
- New remotes start with **zero** buttons. The library creates named **pending**
  commands only after explicit user selection. No cloud metadata or fabricated
  signal is associated with such commands.
- Selective blank-button cleanup may delete only pending, not-verified buttons
  whose local code absence has been confirmed by the backend. An unknown remote
  backend is not evidence of an empty store.
- Renaming a label never changes a bound `remote_name`, source integration,
  stored waveform, profile ID or the selected HA `remote` entity.

The user interface must keep `Add remote` form fields empty until the user
enters a name, chooses an icon and selects a local executor. Do not infer a
device type or preselect a physical gateway.

## Verification

`tests/test_templates.py` asserts complete command coverage, unique
technical keys and visible captions, locale-independent English labels and
non-destructive legacy migration. `tests/test_profile_picker.js` verifies
blank creation fields and guarded form submission. Hardware compatibility
requires real-world learning, sending, restart and offline tests.
