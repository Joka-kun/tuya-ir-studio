# Contributing to Tuya IR Studio

Thanks for helping improve local IR control in Home Assistant. Review [README](README.md), [ROADMAP](ROADMAP.md), and [SECURITY](SECURITY.md) first.

## Before opening an issue

Describe one reproducible defect, the Home Assistant version, Tuya IR Studio version, gateway family/protocol, expected result, actual result and sanitized logs. Never upload Local Keys, tokens, real device IDs, private IP addresses or full `.storage` contents. For hardware issues, distinguish a returned HA service result from an actual physical IR reaction.

## Changes and tests

Use a feature branch and pull request. Keep IR functionality local-first. Do not add inferred cloud key lists or invent IR waveforms. Changes to persistent profiles/CodeStore require backward-compatible migration and tests proving learned codes survive. Do not alter stable hub network settings or attempt upstream HACS catalog submission as a shortcut.

Run:

```bash
python -m pytest -q tests
python -m compileall -q custom_components/ir_studio
node --check custom_components/ir_studio/frontend/panel.js
node tests/test_local_only_ui.js
```

CI also runs Hassfest and HACS validation. For translations, keep Home Assistant config-flow field names consistent with `strings.json`, and make README instructions accurate for the selected language. Third-party code must retain its original license and attribution.

**Merge criteria:** green CI, correct documentation, no untested claims, no user-data loss and clearly identified hardware validation still outstanding.
