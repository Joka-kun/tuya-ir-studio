// Regression for automatic choice of the only available physical HA IR
// executor. Remapping changes profile remote_entity, not IR signals or keys.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('custom_components/ir_studio/frontend/panel.js', 'utf8');
const ctx = {
  HTMLElement: class {}, customElements: {get:()=>null, define:()=>{}}, console
};
vm.createContext(ctx);
vm.runInContext(source + '\nglobalThis.TestPanel = IRStudioPanel;', ctx);

const panel = Object.create(ctx.TestPanel.prototype);
panel._hass = {states:{
  'remote.physical': {state:'off', attributes:{friendly_name:'Bedroom IR'}},
  'remote.virtual': {state:'on', attributes:{ir_studio_virtual:true}},
  'remote.disconnected': {state:'unavailable', attributes:{}},
}};
const profiles = [
  {id:'a',name:'Television',remote_entity:'remote.old',buttons:[{id:'power'}]},
  {id:'b',name:'Projector',remote_entity:'remote.physical',buttons:[{id:'power'}]},
];
const html = panel._backupImportRows(profiles);
assert.equal((html.match(/type="hidden" data-backup-remote=/g)||[]).length,2);
assert.equal((html.match(/value="remote.physical"/g)||[]).length,2);
assert(!html.includes('<select id="backup-remote-'));
assert(!html.includes('Выберите действующий ИК-шлюз'));
assert(html.includes('выбран автоматически'));
assert(html.includes('remote.old'), 'preserve old binding as informative text');
assert(!html.includes('value="remote.virtual"'));
assert(!html.includes('value="remote.disconnected"'));

// Simulate the real HTML controls returned by _backupImportRows: the user
// clicks Import directly, with no manual selection.
const hidden = [...html.matchAll(/<input type="hidden" data-backup-remote="([^"]+)" value="([^"]+)"/g)];
assert.equal(hidden.length,2);
const choices = hidden.map((match)=>({dataset:{backupRemote:match[1]},value:match[2]}));
const calls = [];
let lastToast = '';
panel._selectedBackupIds = ()=>['a','b'];
panel._importBackup = {format:'tuya-ir-studio-backup',format_version:3,profiles};
panel._call = async (type,args)=>{
  calls.push({type,args});
  return {changes:{replaced_profiles:[],added_profiles:['Television'],
    merged_profiles:[],skipped_profiles:[]}};
};
panel._load = async()=>{};
panel._dialogClose = ()=>{};
panel._toast = message=>{lastToast=message;};
panel.shadowRoot = {
  querySelector: key=>key==='#backup-strategy'?{value:'merge'}:null,
  querySelectorAll: key=>key==='[data-backup-remote]'?choices:[],
};
(async()=>{
  await panel._backupImport();
  assert.equal(calls.length,2,'preview and commit both use the automatic binding');
  for (const call of calls) {
    assert.equal(call.type,'backup_import');
    assert.equal(call.args.remote_bindings.a,'remote.physical');
    assert.equal(call.args.remote_bindings.b,'remote.physical');
    assert.equal(call.args.strategy,'merge');
  }
  calls.length=0;
  panel._importBackup = {format:'tuya-ir-studio-backup',profiles};
  choices[0].value='';
  await panel._backupImport();
  assert.equal(calls.length,0,'never perform a partial import if a binding is missing');
  assert(lastToast.includes('Выбери ИК-устройство'));

  // With multiple live physical transmitters, keep a selector and only
  // preselect a stored binding that still refers to a real available entity.
  panel._hass.states['remote.second'] = {
    state:'on',attributes:{friendly_name:'Hall IR'}
  };
  const multiple = panel._backupImportRows(profiles);
  assert.equal((multiple.match(/<select id="backup-remote-/g)||[]).length,2);
  assert(!multiple.includes('type="hidden" data-backup-remote='));
  assert(multiple.includes('Выберите действующий ИК-шлюз'));
  assert(multiple.includes('value="remote.physical"'));
  assert(multiple.includes('value="remote.second"'));
  assert(!multiple.includes('value="remote.virtual"'));
  assert(!multiple.includes('value="remote.disconnected"'));
  // The first old binding is gone, so its select has only placeholder
  // selected; the second binding is still valid and may be reused.
  assert(/<select id="backup-remote-a"[\s\S]*?<option value="" selected disabled>/.test(multiple));
  assert(/<select id="backup-remote-b"[\s\S]*?<option value="remote.physical" selected>/.test(multiple));

  // No usable executor: never silently assign an unavailable/virtual one.
  panel._hass.states['remote.physical'].state='unavailable';
  panel._hass.states['remote.second'].state='unknown';
  const none = panel._backupImportRows(profiles);
  assert(none.includes('Нет доступных ИК-шлюзов'));
  assert(!none.includes('type="hidden" data-backup-remote='));
  assert(!none.includes('выбран автоматически'));

  console.log('Single executor auto-selected; multi/none safe selection: PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
