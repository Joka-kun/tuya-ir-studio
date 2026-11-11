# Home Assistant Marketplace listing and brand images

Tuya IR Studio is a **community-maintained custom integration listed in the
Home Assistant Marketplace** (formerly HACS), not a built-in Home Assistant
integration. Its listing was accepted in
[hacs/default#13600](https://github.com/hacs/default/pull/13600) on
2026-11-09. Install it by searching **Tuya IR Studio** under
**Settings → Marketplace**. The custom-repository option is only a fallback
when the catalog has not refreshed.

## What appears in the Marketplace before installation

- The installed integration uses
  `custom_components/ir_studio/brand/icon.png` (256 × 256) and
  `icon@2x.png` (512 × 512). Optional `dark_icon*.png` use matching
  artwork. The root `brand/` assets mirror those files for older tooling,
  and `frontend/icon.png` is only for IR Studio's own panel.
- **Before installation**, Home Assistant's Marketplace requests icons from
  `https://brands.home-assistant.io/marketplace/ir_studio/icon.png`
  rather than directly from GitHub or the already installed local integration.
  The separate service indexes the `brand/` folder under the integration's
  domain in the latest published GitHub release. See the
  [Home Assistant Marketplace publishing guide](https://contributors.home-assistant.io/marketplace/guides/integrations/)
  and the [brands service README](https://github.com/home-assistant/brands#marketplace-icons).
- The brands service checks the Marketplace integration feed about hourly,
  and rechecks a repository when a new release is seen or after a week. It may
  return **404** for an indexed missing icon or **503** when its availability
  is unknown. Browser and CDN caches can delay visible changes. Do not move
  these custom-integration icons into the legacy home-assistant/brands
  `custom_integrations/` repository.
- A valid image in Git and passing HACS validation do **not** prove the
  public Marketplace image endpoint has been indexed. Do not declare the
  placeholder resolved without a successful `image/png` HTTP response
  from the marketplace-specific URL and a fresh Marketplace UI check.

## Verified Tuya icon delivery — 2026-11-11

A [read-only GitHub Actions probe](../tools/marketplace_icon_probe.py) checked the
latest published `v1.0.8` asset against the **public** Marketplace images,
with `so_diffuser_ble` as a control:

- `https://brands.home-assistant.io/marketplace/ir_studio/icon.png`:
  **HTTP 200**, `image/png`, **256 × 256**.
- `https://brands.home-assistant.io/marketplace/ir_studio/icon@2x.png`:
  **HTTP 200**, `image/png`, **512 × 512**.
- Both PNGs have **identical visible RGBA appearance** to the published Tuya
  icons when composited against either light or dark backgrounds
  (mean absolute RGB error **0.0**). File hashes may differ because
  transparent pixels and PNG encoding can differ without changing the image.
- The Xiaomi `so_diffuser_ble` Marketplace icon passed the same checks.

**Conclusion:** Tuya's published icon and the public Marketplace icon delivery
are both correct as of this check. A missing card on a specific Home Assistant
installation should first be investigated as an **instance/frontend cache or
client connectivity issue**; a blind new release, duplicate brand files or
repeated asset uploads are not supported by this evidence.

Safe UI-level first test: hard-refresh the Marketplace page
(`Ctrl+Shift+R`) or reopen it in a fresh private browsing window.
If the issue persists, inspect the browser request for
`/api/brands/marketplace/ir_studio/dark_icon.png` and Home Assistant's
per-domain cache under `/config/.cache/brands/marketplace/ir_studio` rather
than purging the global brands cache. Do not delete storage entries or
reconfigure integration credentials to fix an icon.

## Required verification before filing an upstream issue

1. Check that `custom_components/ir_studio/brand/icon.png` exists
   **in the latest release tag**, not only in `main`; also verify
   256/512 px PNG integrity. `tests/test_brand.py` checks this, including
   consistency between root and integration brand copies.
2. Open
   [the Marketplace icon endpoint](https://brands.home-assistant.io/marketplace/ir_studio/icon.png)
   directly. Record the HTTP status and content type, without assuming that
   its generic placeholder image is our icon.
3. Refresh the Marketplace catalog and image cache (accounting for its
   hourly indexing and CDN cache). Confirm the actual tile displays the icon
   **before the integration is installed**.
4. If still missing, compare this case with the
   [HACS/frontend missing-icon report](https://github.com/hacs/integration/issues/5402)
   and attach the public release/tag, URL, response status and timestamps
   to a relevant Marketplace or brands issue. Do not upload duplicate brand
   artwork as a workaround.

## Releases and QA

1. Changes go through a PR with the **Unit tests and syntax**,
   **Hassfest**, and **Validate HACS** checks.
2. Only verified merges are released; the publisher checks the exact
   `main` commit against the manifest version and required check results.
3. Local learning and IR transmission must be tested on real hardware.
   A green CI is not proof of physical device response.
4. GitHub's repository **About** one-line description is separate metadata:
   editing this Markdown file does not change that field, or the preview
   image in Marketplace.

**Supported scope:** compatible Tuya / Smart Life IR hubs, local LAN
transmission, real IR learning, custom remotes and backups. QR onboarding
uses only IR Studio's own authorized session and does not import Smart Life
cloud IR layouts or access Tuya Local's private tokens.
