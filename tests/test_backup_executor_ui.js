// The backup executor picker is ALWAYS visible. A single available physical
// remote is preselected, while 2+ remotes require explicit user choice.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('custom_components/ir_studio/frontend/panel.js', 'utf8');
const ctx = {HTMLElement: class {}, customElements:{get:()=>null,define:()=>{}}, console};
vm.createContext(ctx);
vm.runInContext(source + '\nglobalThis.TestPanel=IRStudioPanel;', ctx);
const panel = Object.create(ctx.TestPanel.prototype);
panel._hass = {states:{
  'remote.only': {state:'off', attributes:{friendly_name:'Living room IR'}},
  'remote.virtual': {state:'on', attributes:{ir_studio_virtual:true}},
  'remote.unavailable': {state:'unavailable', attributes:{}},
}};
const profiles = [
  {id:'a',name:'Old TV',remote_entity:'remote.stale',buttons:[{id:'power'}]},
  {id:'b',name:'Lamp',remote_entity:'remote.only',buttons:[{id:'toggle'}]},
];
const once = panel._backupImportRows(profiles);
assert.equal((once.match(/<select id="backup-remote-/g)||[]).length,2,
  'a dropdown must remain visible for every backup profile even with one hub');
assert.equal((once.match(/data-backup-remote="/g)||[]).length,2);
assert(!once.includes('type="hidden" data-backup-remote='));
assert.equal((once.match(/<option value="remote.only" selected>/g)||[]).length,2,
  'the sole physical hub must be preselected for every profile');
assert(once.includes('выбран автоматически'));
assert(once.includes('remote.stale'), 'retain old entity ID as informational label');
assert(!once.includes('value="remote.virtual"'));
assert(!once.includes('value="remote.unavailable"'));

// The actual selected option in the visible dropdown is sent to preview AND
// commit without an extra user click.
const selectMatches = [...once.matchAll(/<select id="backup-remote-([^"]+)" data-backup-remote="([^"]+)">([\s\S]*?)<\/select>/g)];
assert.equal(selectMatches.length,2);
const choices = selectMatches.map(match=>{
  const selected = match[3].match(/<option value="([^"]*)" selected>/);
  assert(selected, 'no preselected executor in real select');
  return {dataset:{backupRemote:match[2]},value:selected[1]};
});
const calls=[];
let lastToast='';
panel._selectedBackupIds=()=>['a','b'];
panel._importBackup={format:'tuya-ir-studio-backup',format_version:3,profiles};
panel._call=async(type,args)=>{
  calls.push({type,args});
  return {changes:{replaced_profiles:[],added_profiles:['Old TV'],
    merged_profiles:[],skipped_profiles:[]}};
};
panel._load=async()=>{};
panel._dialogClose=()=>{};
panel._toast=s=>{lastToast=s};
panel.shadowRoot={
  querySelector:key=>key==='#backup-strategy'?{value:'merge'}:null,
  querySelectorAll:key=>key==='[data-backup-remote]'?choices:[],
};

(async()=>{
  await panel._backupImport();
  assert.equal(calls.length,2);
  for (const call of calls) {
    assert.equal(call.args.remote_bindings.a,'remote.only');
    assert.equal(call.args.remote_bindings.b,'remote.only');
    assert.equal(call.args.strategy,'merge');
  }
  calls.length=0;
  panel._importBackup={format:'tuya-ir-studio-backup',profiles};
  choices[0].value='';
  await panel._backupImport();
  assert.equal(calls.length,0,'must not import partially with unselected executor');
  assert(lastToast.includes('Выбери ИК-устройство'));

  // Several: dropdown stays visible, no choice preselected, because user
  // explicitly asked to select the executor even if the backup ID still exists.
  panel._hass.states['remote.second'] = {
    state:'on',attributes:{friendly_name:'Bedroom IR'}
  };
  const multiple = panel._backupImportRows(profiles);
  assert.equal((multiple.match(/<select id="backup-remote-/g)||[]).length,2);
  assert.equal((multiple.match(/<option value="" selected disabled>/g)||[]).length,2);
  assert(!multiple.includes('<option value="remote.only" selected>'));
  assert(!multiple.includes('<option value="remote.second" selected>'));
  assert(multiple.includes('value="remote.second"'));
  assert(!multiple.includes('выбран автоматически'));
  assert(!multiple.includes('type="hidden" data-backup-remote='));

  // No available transmitter: show a visible selector with no valid option.
  panel._hass.states['remote.only'].state='unknown';
  panel._hass.states['remote.second'].state='unavailable';
  const none = panel._backupImportRows(profiles);
  assert.equal((none.match(/<select id="backup-remote-/g)||[]).length,2);
  assert(none.includes('Нет доступных ИК-шлюзов'));
  assert(!none.includes('type="hidden" data-backup-remote='));
  assert(!none.includes('выбран автоматически'));
  console.log('Backup: visible dropdown, sole-device auto-choice, multi-device manual selection: PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
