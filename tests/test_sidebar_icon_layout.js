// Layout contract for Home Assistant ha-icon, including its internal SVG size.
// The former bug enlarged the outer box but left --mdc-icon-size at 23px.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const src = fs.readFileSync('custom_components/ir_studio/frontend/panel.js', 'utf8');
const icons = JSON.parse(fs.readFileSync('custom_components/ir_studio/icon_catalog.json', 'utf8')).icons;
const ctx = {HTMLElement: class {}, customElements: {get: () => null, define: () => {}}, console};
vm.createContext(ctx);
vm.runInContext(src +
  '\nglobalThis.setCatalog=setIconCatalog;globalThis.glyph=profileGlyph;', ctx);
ctx.setCatalog(icons);

function rule(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = src.match(new RegExp('(?:^|\\n)\\s*' + escaped + '\\{([^}]*)\\}'));
  assert(match, 'Missing style rule: ' + selector);
  return match[1];
}

const base = rule('.device-icon');
assert(base.includes('display:grid;place-items:center'));
assert(base.includes('--mdc-icon-size:var(--studio-icon-size,23px)'));
assert(base.includes('width:var(--studio-icon-size,23px)'));
assert(base.includes('height:var(--studio-icon-size,23px)'));

const sizes = [
  ['.profile-heading-glyph', 36],
  ['.profile-symbol', 23],
  ['.empty-state-icon', 40],
  ['.icon-choice', 27],
  ['.cloud-remote-icon', 24],
  ['.type-preview', 25],
  ['.modal-heading-icon', 30],
];
for (const [selector, pixels] of sizes) {
  const css = rule(selector);
  assert(css.includes('--studio-icon-size:' + pixels + 'px'),
    'Wrong internal glyph size for ' + selector);
}
const heading = rule('.profile-heading-glyph');
assert(heading.includes('place-items:center'));
assert(heading.includes('width:53px;height:53px'));
assert(src.includes('.profile-heading-glyph{--studio-icon-size:29px;width:43px;height:43px}'),
  'Mobile header icon must scale inside its smaller tile');

// Prevent regression to setting dimensions only on the host without
// updating the ha-icon SVG size.
assert(!/\.profile-heading-glyph \.device-icon\s*\{\s*width:/.test(src));
assert(!/\.profile-symbol \.device-icon\s*\{\s*width:/.test(src));
assert(!src.includes('Sixty MDI icons'));

const known = ctx.glyph({icon:'lamp',name:'Table lamp'});
assert(known.includes('ha-icon class="device-icon"'));
assert(known.includes('mdi:chandelier'));
const custom = ctx.glyph({icon_mdi:'mdi:television-classic',icon:'blank_remote'});
assert(custom.includes('mdi:television-classic'));
assert(!custom.includes('mdi:remote"'));

console.log('Centered scalable HA icon contract across sidebar, selected remote and dialogs passed');
