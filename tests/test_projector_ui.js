// Settings save only the independent icon while preserving Remote code identities.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const src=fs.readFileSync('custom_components/ir_studio/frontend/panel.js','utf8');
const icons=JSON.parse(fs.readFileSync('custom_components/ir_studio/icon_catalog.json','utf8')).icons;
const ctx={HTMLElement:class{},customElements:{get:()=>null,define:()=>{}},console};
vm.createContext(ctx);
vm.runInContext(src+'\nglobalThis.Panel=IRStudioPanel;',ctx);
(async()=>{
  const p={id:'existing',name:'Projector',buttons:[{id:'b',name:'Play',remote_name:'Play'}],
    profile_type:'projector',account_ref:'legacy',remote_entity:'remote.test'};
  const panel=Object.create(ctx.Panel.prototype);
  panel._data={profiles:[p],icons};
  panel._filter='';
  panel._selected=()=>p;
  panel._language=()=>'ru';
  panel._remOptions=()=>'<option value="remote.test" selected>YRC11</option>';
  panel._toast=()=>{};
  panel._load=async()=>{};
  const row={html:''};
  const form={querySelector:sel=>({
    '#settings-name':{value:'Projector'},
    '#settings-icon':{value:'lamp'},
    '#settings-remote':{value:'remote.test'},
  }[sel])};
  panel.shadowRoot={querySelector:sel=>sel==='#command-list'?row:sel==='#modal'?form:null};
  panel._setHTML=(host,html)=>{host.html=html};
  panel._renderRows();
  assert(row.html.includes('Play'));
  assert(!row.html.includes('fill-profile'));
  panel._dialog=html=>{panel.modalHTML=html};
  panel._showProfileSettings();
  assert(panel.modalHTML.includes('Настройки пульта'));
  assert(panel.modalHTML.includes('Иконка пульта'));
  assert(panel.modalHTML.includes('id="settings-icon"'));
  assert(panel.modalHTML.includes('data-action="delete-profile"'));
  assert(panel.modalHTML.includes('data-action="save-profile-settings"'));
  assert(!panel.modalHTML.includes('Показать ручной ввод кодов'));
  assert(!panel.modalHTML.includes('Тип устройства'));
  assert(!panel.modalHTML.includes('200 уникальных'));
  assert.equal((panel.modalHTML.match(/data-icon-choice=/g)||[]).length,200);
  const calls=[];
  panel._call=async(type,payload)=>{calls.push({type,payload});return {}};
  panel._dialogClose=()=>{};
  await panel._saveProfileSettings();
  assert.equal(calls.length,1);
  assert.equal(calls[0].type,'profile_set_icon');
  assert.equal(calls[0].payload.icon,'lamp');
  assert(!calls.some(c=>c.type==='profile_set_type'||c.type==='profile_bind'||c.type==='profile_apply_template'));
  assert.equal(p.buttons[0].remote_name,'Play');
  console.log('Independent icon settings and safe deletion placement passed');
})().catch(e=>{console.error(e);process.exitCode=1});
