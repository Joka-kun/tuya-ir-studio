// Contract: QR credentials are IR Studio-owned; no user-facing claim of
// borrowing Tuya Local or another integration's Tuya / Smart Life login.
const assert = require('node:assert/strict');
const fs = require('node:fs');
for (const lang of ['en','ru','de','es','fr','zh']) {
  const path = 'custom_components/ir_studio/translations/' + lang + '.json';
  const data = JSON.parse(fs.readFileSync(path,'utf8'));
  const desc = data.config.step.user.description;
  const label = data.selector.setup_mode.options.cloud;
  assert.equal(typeof desc,'string',lang);
  assert.equal(typeof label,'string',lang);
  const copy = desc + ' ' + label;
  const forbidden = /reuse an existing Tuya|существующую авторизацию Tuya|vorhandene Tuya\/Smart-Life-Anmeldung|sesión Tuya\/Smart Life existente|session Tuya\/Smart Life existante|复用 Tuya\/Smart Life 登录/;
  assert(!forbidden.test(copy), 'Misleading cross-integration QR login in ' + lang);
  assert(/IR Studio/i.test(copy), 'Explicit IR Studio-owned QR session absent: ' + lang);
}
for (const readme of ['README.md','README_RU.md']) {
  const text = fs.readFileSync(readme,'utf8');
  assert(/Marketplace/.test(text), 'Home Assistant Marketplace instructions missing: ' + readme);
  assert(/(?:Settings|Настройки)\s*→\s*Marketplace/.test(text),
    'Settings → Marketplace should be the primary install path: ' + readme);
  assert(/(?:search|найди)/i.test(text),
    'Integration search should be documented: ' + readme);
  assert(!/Custom repositories|Пользовательские репозитории/.test(text),
    'Outdated manual repository installation should be removed: ' + readme);
}
const core = fs.readFileSync('custom_components/ir_studio/tuya_cloud.py','utf8');
assert(!core.includes('hass.data.get("tuya_local"'));
assert(!core.includes("hass.data.get('tuya_local'"));
const pkg = JSON.parse(fs.readFileSync('custom_components/ir_studio/manifest.json','utf8'));
assert.equal(pkg.version,'1.0.8');
console.log('Own QR session wording across six locales and manifest: PASS');
