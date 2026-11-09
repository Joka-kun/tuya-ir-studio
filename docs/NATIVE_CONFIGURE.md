# IR Studio without a sidebar — native Home Assistant workflow

The default setup for a new native Tuya IR hub uses the built-in **Configure**
button on the integration card, not a custom Home Assistant panel.

## Add and learn a remote

1. **Settings → Devices & services → Tuya IR Studio → Configure**.
2. Choose **Add remote**, type its name. If several physical IR transmitters
   are available, choose one. The current hub is selected by default.
3. Home Assistant registers the virtual remote as a device, without adding
   speculative or blank commands.
4. Select **Learn a command**, enter the original physical button's name
   (for example `Power`, `VOL +`, `Mute`), and follow the progress prompt.
5. The button-name field offers searchable English suggestions from the
   command library, but arbitrary names are also accepted. These suggestions
   never contain or import IR signals.
6. **Manage existing remote → Manage button → Rename** edits only the displayed
   label; the hidden command key, recorded IR signal and unique entity ID are stable.
7. **Manage existing remote → Choose icon** opens Home Assistant's own visual
   MDI selector with live previews. You can also choose an icon when creating
   a remote. Icons do not change its commands or IR codes.
8. Only a successfully learned/stored command is eligible to become a HA
   `button` entity. A third-party driver that doesn't expose its code store
   may require verification rather than being marked stored without evidence.
9. In the device page use the button, or automate via `button.press` and
   `remote.send_command` using the assigned entity IDs.

The physical transmitter `remote.*` remains distinct from the virtual
remote of each appliance. Internal `remote_device` and `remote_name` values
are immutable when the visible caption is renamed.

## Edit or remove

**Configure → Manage existing remote → Manage button** lets you choose one
button and perform **Test send**, **Relearn**, **Rename** or **Delete**. Testing
asks for confirmation and sends exactly one signal (without guessing whether
the appliance reacted). Relearning keeps the same button/HA entity identity
and uses its original immutable IR command key.

**Configure → Manage existing remote → Choose icon** uses Home Assistant's own
visual MDI picker, with actual icon previews. The advanced side panel's curated icons remain available
but are not required. The selected icon is stored with the profile and is
included in local backups.

**Configure → Manage existing remote** also supports renaming the remote or
deleting the entire profile with confirmation. Deletion
removes IR Studio-owned metadata/code entries; it **does not delete** any raw
codes stored in an independent physical remote driver's own CodeStore.

## Backup-restored command status

The advanced sidebar distinguishes commands that have a locally known waveform
(`stored`, `verified`, or visible in an IR Studio-owned Store) from commands
restored with `needs_check`. Its left profile counter counts both categories,
and explicitly says how many restored commands still need verification. The
latter are *not* marked physically verified, and are not automatically put into
the re-learning wizard just because a foreign remote driver's private CodeStore
cannot be inspected. Existing imported profiles are covered without reimport.

A successful `remote.send_command` call is not proof that the appliance acted.
Use the normal send + physical-confirmation action to mark a command verified.

## Advanced editor

**Configure → Interface → Show advanced IR Studio panel in sidebar** toggles
the old editor. New native hub installations default to **off**; older
installations retain their existing panel until switched off by the user.

The advanced panel remains available for compatible `.ir` import, library
templates, bulk learning and portable backups. The panel's JavaScript is not
opened or loaded by the browser during ordinary Home Assistant use.

## Design constraints

- An HA `button` entity is for **pressing a known command**, not for opening
  a setup dialog. The Configure action is the correct built-in entry point.
- `remote.turn_on` changes the logical remote entity; it is not an appliance
  `Power` command. Use the learned button instead.
- Never assume an IR transmitter confirms that the appliance reacted.
- Do not convert IR remotes into stateful `light`, `switch` or `climate`
  entities without an explicit state model and appropriate feedback.
- A Home Assistant full backup is recommended before upgrading major entity
  management behavior. Existing profiles, unique IDs and code stores are
  preserved across the options-flow migration.
