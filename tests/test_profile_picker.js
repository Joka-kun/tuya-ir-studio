// One icon library, no duplicated physical glyphs and no device-type coupling.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const src = fs.readFileSync('custom_components/ir_studio/frontend/panel.js', 'utf8');
const icons = JSON.parse(fs.readFileSync('custom_components/ir_studio/icon_catalog.json', 'utf8')).icons;
const ctx = {HTMLElement: class {}, customElements: {get:()=>null,define:()=>{}}, console};
vm.createContext(ctx);
vm.runInContext(src+'\nglobalThis.PanelForTest=IRStudioPanel;globalThis.showIconForTest=deviceIcon;globalThis.setIconsForTest=setIconCatalog;globalThis.glyphForTest=profileGlyph;',ctx);
assert.equal(icons.length,200);
assert.equal(new Set(icons.map(x=>x.id)).size,200);
assert.equal(new Set(icons.map(x=>x.mdi)).size,200);
ctx.setIconsForTest(icons);
for(const icon of icons) assert(ctx.showIconForTest(icon.id).includes('mdi:'+icon.mdi));
assert(ctx.showIconForTest('tv_standard')!==ctx.showIconForTest('tv_smart'));
assert(ctx.showIconForTest('lamp')!==ctx.showIconForTest('white_dimmer'));
assert(ctx.showIconForTest('projector')!==ctx.showIconForTest('projector_screen'));
assert(ctx.glyphForTest({icon:'lamp',profile_type:'tv_standard'}).includes('mdi:chandelier'));
assert(ctx.glyphForTest({profile_type:'projector'}).includes('mdi:projector'));

function mockPanel(language) {
  const panel=Object.create(ctx.PanelForTest.prototype);
  panel._hass={locale:{language},states:{
    'remote.yrc11':{state:'off',attributes:{friendly_name:'YRC11'}}
  }};
  panel._data={icons,profiles:[]};
  panel._dialog=html=>{panel.html=html};
  panel.shadowRoot={querySelector:()=>null};
  return panel;
}
for(const language of ['ru-RU','en-US']){
  const panel=mockPanel(language);
  panel._showCreateProfile();
  assert(panel.html.includes('id="create-icon"'));
  assert(panel.html.includes('id="create-icon" value=""'));
  assert(panel.html.includes('id="profile-name" value=""'));
  assert(!panel.html.includes('<option value="" selected disabled>Выбрать ИК-шлюз</option>'));
  assert(panel.html.includes('value="remote.yrc11" selected'));
  assert(panel.html.includes('Доступный ИК-шлюз выбран автоматически'));
  assert(panel.html.includes('data-action="create-profile" disabled'));
  assert(!panel.html.includes('value="Новый пульт"'));
  assert(!panel.html.includes('value="New remote"'));
  assert(!panel.html.includes('60 уникальных'));

  assert(!panel.html.includes('200 уникальных'));
  assert(!panel.html.includes('200 unique'));
  assert(panel.html.includes('Иконка пульта'));
  assert(!panel.html.includes('Тип устройства'));
  assert(!panel.html.includes('id="preset"'));
  assert.equal((panel.html.match(/data-icon-choice=/g)||[]).length,200);
  assert(panel.html.includes('data-icon-search='));
  assert(panel.html.includes('icon="mdi:projector"'));
}
assert(!src.includes('SIMPLE_PROFILE_TYPES'));
assert(!src.includes('DEVICE_ICON_PATHS'));
assert(!src.includes('data-action="toggle-advanced"'));
console.log('200 unique icon glyphs and creation picker RU/EN passed');


// The actual form must stay disabled until all three fields are selected.
{
  const panel=mockPanel('ru-RU');
  const fields={'#profile-name':{value:''},'#create-icon':{value:''},
    '#profile-remote':{value:'remote.yrc11'},'[data-action="create-profile"]':{disabled:false}};
  const form={querySelector:key=>fields[key]};
  panel.shadowRoot={querySelector:key=>key==='#modal'?form:null};
  panel._showCreateProfile();
  assert.equal(fields['[data-action="create-profile"]'].disabled,true);
  fields['#profile-name'].value='Спальня';
  assert.equal(panel._updateCreateProfileValidity(),false);
  fields['#create-icon'].value='tv_standard';
  assert.equal(panel._updateCreateProfileValidity(),true);
  assert.equal(fields['[data-action="create-profile"]'].disabled,false);
  fields['#profile-name'].value='  ';
  assert.equal(panel._updateCreateProfileValidity(),false);
  fields['#profile-name'].value='Спальня';
  fields['#create-icon'].value='not-in-catalog';
  assert.equal(panel._updateCreateProfileValidity(),false);
}


// Default: on first, off is healthy idle, unknown/unavailable are never
// silently selected; an explicit user choice always wins while usable.
{
  const panel=mockPanel('ru-RU');
  panel._hass.states={
    'remote.bad':{state:'unavailable',attributes:{friendly_name:'Disconnected'}},
    'remote.idle':{state:'off',attributes:{friendly_name:'Idle Tuya IR'}},
    'remote.active':{state:'on',attributes:{friendly_name:'Active IR'}},
    'remote.unknown':{state:'unknown',attributes:{friendly_name:'Unknown'}}
  };
  assert.equal(panel._defaultRemoteId(),'remote.active');
  panel._showCreateProfile();
  assert(panel.html.includes('value="remote.active" selected'));
  assert(panel.html.includes('value="remote.idle"'));
  assert(!panel.html.includes('value="" selected disabled>Выбрать ИК-шлюз'));

  panel._selectedSource='remote.idle';
  assert.equal(panel._defaultRemoteId(),'remote.idle');
  panel._showCreateProfile();
  assert(panel.html.includes('value="remote.idle" selected'));
  panel._selectedSource='remote.bad';  // An unavailable prior choice is ignored.
  assert.equal(panel._defaultRemoteId(),'remote.active');

  panel._selectedSource='';
  panel._data.profiles=[{id:'p1',remote_entity:'remote.idle'}];
  panel._active='p1';
  assert.equal(panel._defaultRemoteId(),'remote.idle');
  panel._active=null;
  panel._data.profiles=[];
  panel._hass.states['remote.active'].state='unavailable';
  assert.equal(panel._defaultRemoteId(),'remote.idle');
  panel._hass.states['remote.idle'].state='unknown';
  assert.equal(panel._defaultRemoteId(),'');
  panel._showCreateProfile();
  assert(panel.html.includes('<option value="" selected disabled>Выбрать ИК-шлюз</option>'));
}

// Changing the dropdown must not lock it: the selected source is remembered
// when a new creation dialog opens, but can be changed again freely.
{
  const panel=mockPanel('ru-RU');
  panel._hass.states['remote.other']={state:'on',attributes:{friendly_name:'Other IR'}};
  const events={};
  const fields={
    '#profile-name':{value:'Bedroom',addEventListener(name,fn){events.name=fn}},
    '#create-icon':{value:'projector'},
    '#profile-remote':{value:'remote.other',addEventListener(name,fn){events.remote=fn}},
    '[data-action="create-profile"]':{disabled:true},
  };
  panel.shadowRoot={querySelector:key=>key==='#modal' ? {querySelector:sub=>fields[sub]} : null};
  panel._showCreateProfile();
  assert.equal(fields['[data-action="create-profile"]'].disabled,false);
  assert.equal(typeof events.remote,'function');
  events.remote();
  assert.equal(panel._selectedSource,'remote.other');
  fields['#profile-remote'].value='remote.yrc11';
  events.remote();
  assert.equal(panel._selectedSource,'remote.yrc11');
  assert.equal(panel._defaultRemoteId(),'remote.yrc11');
}
