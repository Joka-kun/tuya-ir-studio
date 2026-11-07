# Tuya IR Studio — Roadmap and acceptance

[English](README.md) · [Русский](README_RU.md) · [Changelog](CHANGELOG.md) · [Home Assistant entity model](docs/HA_ENTITY_MODEL.md)

The project is a local infrared remote manager for Home Assistant. QR / Smart Life onboarding retrieves gateway access details; it does **not** import Smart Life button layouts or IR waveforms.

## Implemented and covered by automated tests

- [x] Direct Tuya LAN gateway setup using QR-assisted or manual credentials; saved QR authorization can be reused.
- [x] Virtual HA Device and `remote` per profile, with `button` entities for learned commands. User-facing captions, entity IDs and physical IR namespaces are independent.
- [x] Native **Configure** wizard for profiles and individual buttons (learn, test, relearn, rename, delete), plus an optional advanced sidebar for bulk workflows, Flipper `.ir` import and backups.
- [x] 164 named library commands, with no fabricated code; curated sidebar icons and the native HA MDI picker affect presentation only.
- [x] One scalable, centered SVG sizing convention for selected-remote headers, sidebar cards, dialogs, previews and empty states. Mobile size is set separately but follows the same convention.
- [x] Reorder virtual remote profiles in the optional sidebar by touch/mouse drag on a single ⠿ handle, or keyboard ArrowUp / ArrowDown on that focused handle; persist order to the existing HA profile Store without altering codes or entity identifiers.
- [x] Physical command transmission is serialized. Native Tuya IR performs a readiness check before the first send / after idle, without automatically repeating an uncertain IR write.
- [x] Conservative cleanup for obsolete placeholders and orphaned virtual HA devices. Learned raw codes, physical hubs and third-party stores are not silently deleted.
- [x] Python and JavaScript regression tests, Hassfest and HACS Validation, with tests for supported Python runtimes.
- [x] Bilingual native setup and options labels for EN/RU; additional onboarding translations are preserved where available.

## Pending hardware acceptance

These are **not** proven by CI. Complete them against a real YRC11 and at least one other supported gateway/firmware when available.

- [ ] Connect by QR and by manual local credentials; verify discovery, restart, authorization persistence and offline operation without changing the working router.
- [ ] Create and rename a virtual remote; teach three distinct commands; confirm HA button entities, stable unique IDs and backup/restore mappings.
- [ ] Verify cold-first-send behavior after at least ten minutes of idle. Compare repeated single sends of a toggle button with the previous driver and confirm **no duplicate** physical presses.
- [ ] Check the advanced sidebar icon visually at desktop and narrow/mobile widths, including custom MDI icons and the high-contrast/dark theme. Confirm that glyphs remain centered and fully visible.
- [ ] Confirm remote/button deletion removes only its matching virtual HA Device Registry entries and does not remove the physical transmitter or learned waveforms held by other drivers.
- [ ] Test failed learning, cancellation, gateway disconnection, reconnect and subsequent sends without silent retries.
- [ ] Review gateway-specific protocol limitations (DPS 201/202, child node, TinyTuya) and document exact supported firmware.

## Future work, gated on the evidence above

- Hardware-verified error categories for LAN write, DP202 timeout and physical target non-response.
- Better diagnostics without logging raw signals, secrets or authentication tokens.
- Translate the complete native **Configure** wizard beyond English and Russian only if maintainers can verify those locales; existing DE/ES/FR/ZH config onboarding translations stay available.
- Consider official HACS Marketplace submission only after device acceptance and review.

## Explicitly outside scope

No guessed IR waveforms, QR-based import of Smart Life button lists, cloned Smart Life layouts, automatic stateful light/switch entities without feedback, or forced changes to the user's existing Home Assistant / LAN setup.

**Safety rule:** preserve Local Keys, active config entries, learned signals, profile/button UUIDs and existing automations. Never confuse successful CI with a verified physical IR transmission.
