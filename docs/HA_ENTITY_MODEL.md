# Home Assistant entity model

## Why a profile is a Home Assistant device

The IR Studio panel is a command editor and learning interface, not a
replacement for native Home Assistant entities.

Each created profile is registered by Home Assistant as a **Device**:

- One virtual `remote` entity: `remote.<profile_name>` (actual entity ID is
  assigned by the HA entity registry and can differ).
- One native `button` entity **only for each learned/stored/verified command**,
  such as `button.<profile_name>_power`. Pending empty commands are not exposed.
- The physical IR transmitter has its **own** distinct `remote` entity.

Stable identifiers use `profile.id` for the device and virtual remote, and
`(profile.id, button.id)` for learned button entities. User-facing renaming
must never change these identifiers, the bound `remote_device` namespace or
stored IR code keys.

## How an automation sends a command

Use a Button action for one preconfigured key:

```yaml
action: button.press
target:
  entity_id: button.table_lamp_power
```

Or directly through the virtual remote:

```yaml
action: remote.send_command
target:
  entity_id: remote.table_lamp
data:
  command: Power
```

The entity IDs above are **illustrative**, not guaranteed. Read the assigned
IDs from **Settings → Devices & services → Tuya IR Studio → Devices**.

The virtual remote is only a logical command target. It delegates to the
selected physical HA remote entity using the original device namespace and
command key. `remote.turn_on` / `remote.turn_off` toggle the *logical remote*
state; they do not send `Power` to the TV, light or air conditioner.

IR is normally **one-way**. Pressing a command does not prove the appliance
received it and does not provide its actual on/off, volume, brightness or
temperature state. Do not create an assumed-state `light`, `switch` or
`climate` entity without an explicit user-approved state model and hardware
feedback where available.

## Ownership and life cycle

One currently active integration entry owns the profile entities. An already
loaded/starting manager is preferred; otherwise an available native hub can
own them. The chosen owner is held for that Home Assistant runtime, so a
second hub does not create duplicate entity IDs. An unreachable hub cannot
be selected as owner. When the owner is removed, a remaining active entry
is reloaded to take over.

All profile and command unique IDs are based on stable profile/button UUIDs,
never on the selected gateway or profile display names.

IR Studio's dispatcher creates newly learned button entities and removes
deleted profiles/buttons. Underlying physical IR codes are not deleted simply
because a HA entity is removed.

Use **Settings → Devices & services → Tuya IR Studio → Configure** to add a remote, learn commands, rename or delete them. The old sidebar is an opt-in advanced editor for batch workflows, backup and specialized formats. Everyday automation uses the same HA device pages, scripts, scenes and voice actions.

## Synchronous disk I/O

The integration reads static JSON catalogs with
`await hass.async_add_executor_job(...)`; no `Path.read_text()` runs in
the event loop during startup. Backup WebSocket commands use already loaded
metadata.

## Recorder entity-history conflict

A warning such as *Cannot migrate history for entity_id ... because the new
entity_id is already in use* means that **Recorder already has history indexed
under the destination name**. This is distinct from a platform unique-ID
collision and does not by itself prove HA entities have failed to load.

Do not delete SQLite rows, `core.entity_registry`, or Recorder data from a
live system. First inspect current entity IDs in HA, preserve the desired
IDs, and take a full HA backup. If historical continuity matters, review
`states_meta` and related Recorder tables using an **offline copy** and a
version-specific migration plan. A mere rename does not automatically merge
two non-empty history streams.
