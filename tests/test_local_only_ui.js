// v1.0: local IR only, no misleading Tuya Cloud remote import.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const src = fs.readFileSync('custom_components/ir_studio/frontend/panel.js','utf8');
const ws = fs.readFileSync('custom_components/ir_studio/websocket.py','utf8');
assert(!src.includes('data-action="account-import"'));
assert(!src.includes('data-action="toggle-advanced"'));
assert(!src.includes('Показать ручной ввод кодов'));
assert(!src.includes('data-action="import-modal"'));
assert(src.includes('data-action="delete-profile"'));
assert(src.includes('profile_set_icon'));
assert(!src.includes('_showAccountDeviceCatalog'));
assert(!src.includes('По данным Tuya'));
assert(!src.includes('Импорт переносит названия кнопок, но не ИК-сигналы'));
assert(!src.includes('Каталог реальных виртуальных ИК-пультов аккаунта.'));
assert(!src.includes('Выбери облачный пульт'));
assert(!src.includes('ИК-пульты Smart Life'));
assert(!src.includes('Импорт кнопок из Tuya JSON'));
assert(!src.includes("_call('ir_catalog')"));
assert(!ws.includes('ws_account_import'));
assert(!ws.includes('ws_ir_import_keys'));
assert(!ws.includes('ws_ir_import_codes'));
assert(!ws.includes('ws_account_qr_start'));
const ctx={HTMLElement:class{},customElements:{get:()=>null,define:()=>{}},console};
vm.createContext(ctx);
vm.runInContext(src+'\nglobalThis.Panel=IRStudioPanel;',ctx);
const panel=Object.create(ctx.Panel.prototype);
panel._data={profiles:[{
 id:'p',name:'New remote',remote_entity:'remote.yrc11',source:'ir_studio',
 buttons:[],template_id:'blank_remote'
}],template_catalog:{button_sets:[],commands:{}}};
panel._active='p';
panel._findTemplate=()=>null;
panel._filter='';
panel._pending=null;
panel._remotes=()=>[{id:'remote.yrc11',name:'YRC11',status:'on'}];
panel._remOptions=()=>'<option value="remote.yrc11">YRC11</option>';
panel._language=()=> 'ru';
panel._dialog=html=>{panel.html=html};
const host={};panel.shadowRoot={querySelector:s=>s==='#command-list'?host:null};
panel._setHTML=(el,html)=>{el.html=html};
panel._renderRows();
assert(host.html.includes('Пульт пока пустой'));
assert(host.html.includes('Добавь нужные кнопки вручную'));
assert(host.html.includes('button-library'));
panel._showButtonLibrary();
assert(panel.html.includes('Библиотека команд'));
console.log('Local-only IR Studio panel, library, and learning UI passed');
