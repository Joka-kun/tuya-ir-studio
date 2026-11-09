// Test actual sidebar import flow: stale saved IDs need an explicit live
// physical transmitter choice; don't accidentally bind to virtual remotes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('custom_components/ir_studio/frontend/panel.js', 'utf8');
const ctx = {HTMLElement: class {},customElements:{get:()=>null,define:()=>{}},console};
vm.createContext(ctx);
vm.runInContext(source+'\nglobalThis.TestPanel = IRStudioPanel;',ctx);

const p = Object.create(ctx.TestPanel.prototype);
p._hass = {states:{
 'remote.physical': {state:'off',attributes:{friendly_name:'Bedroom IR'}},
 'remote.virtual': {state:'on',attributes:{ir_studio_virtual:true}},
 'remote.disconnected': {state:'unavailable',attributes:{}}
}};
const backupProfiles = [
 {id:'a',name:'Television',remote_entity:'remote.old',buttons:[{id:'b'}]},
 {id:'b',name:'Projector',remote_entity:'remote.physical',buttons:[{id:'b'}]}
];
const html = p._backupImportRows(backupProfiles);
assert(html.includes('data-backup-remote="a"'));
assert(html.includes('data-backup-remote="b"'));
assert(html.includes('value="remote.physical"'));
assert(!html.includes('value="remote.virtual"'));
assert(!html.includes('value="remote.disconnected"'));
assert(html.includes('remote.old'));
assert(html.includes('Выберите действующий ИК-шлюз'));
assert(html.includes('id="backup-remote-b"'));

let calls=[];
let lastToast='';
p._selectedBackupIds=()=>['a','b'];
p._importBackup={format:'tuya-ir-studio-backup',format_version:3,profiles:backupProfiles};
p._call=async (type,args)=>{
  calls.push({type,args});
  return type==='backup_import'?
    {changes:{replaced_profiles:[],added_profiles:['Television'],merged_profiles:[],skipped_profiles:[]}}
    : {};
};
p._load=async()=>{};
p._dialogClose=()=>{};
p._toast=(s)=>{lastToast=s;};
const selections=[
 {dataset:{backupRemote:'a'},value:'remote.physical'},
 {dataset:{backupRemote:'b'},value:'remote.physical'}
];
p.shadowRoot = {
  querySelector:(key)=>key==='#backup-strategy'?{value:'merge'}:null,
  querySelectorAll:(key)=>key==='[data-backup-remote]'?selections:[]
};
(async()=>{
 await p._backupImport();
 assert.equal(calls.length,2);
 for(const call of calls){
   assert.equal(call.type,'backup_import');
   assert.equal(call.args.remote_bindings.a,'remote.physical');
   assert.equal(call.args.remote_bindings.b,'remote.physical');
   assert.equal(call.args.strategy,'merge');
 }
 calls=[];
 p._importBackup={format:'tuya-ir-studio-backup',profiles:backupProfiles};
 selections[0].value='';
 await p._backupImport();
 assert.equal(calls.length,0,'no partial import with an unbound profile');
 assert(lastToast.includes('Выбери ИК-устройство'));
 console.log('Backup import requires explicit HA remote executor mapping: PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
