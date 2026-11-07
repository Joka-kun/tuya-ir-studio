# Releases and HACS visibility

Tuya IR Studio is distributed as a **custom HACS repository**. It is not automatically listed in the official HACS default catalog.

## Brand assets

- Repository and integration branding use matching 256px / 512px PNG icons in `brand/` and `custom_components/ir_studio/brand/`.
- The Home Assistant sidebar icon is `custom_components/ir_studio/frontend/icon.png`.
- The GitHub README uses `assets/banner.svg` and `assets/workflow.svg`.
- `tests/test_brand.py` checks asset integrity and matching icon variants.

An icon in an installed integration does **not** prove the integration is listed in the public HACS catalog.

## Verified publishing

1. Changes are reviewed in a pull request. Required checks: **Unit tests and syntax**, **Hassfest**, **Validate HACS**.
2. Once merged, the release workflow verifies that all three **push** checks have passed for the current `main` commit.
3. A GitHub Release is created from the matching manifest version and tested commit. Existing historical Git commit records remain intact.
4. Validate HACS custom-repository installation, the updated icon and sidebar, then physically test learning/transmission on compatible hardware.
5. Official HACS catalog submission is a separate process requiring relevant real-device acceptance; do not submit a fork as a shortcut.

**Current testing boundary:** CI verifies structure and unit contracts, not the physical infrared response of every gateway/firmware.
