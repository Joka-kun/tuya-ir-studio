// Behavioral tests for local-only, 60-second inline infrared learning.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('custom_components/ir_studio/frontend/panel.js', 'utf8');
const ctx = {
  HTMLElement: class {},
  customElements: {get:()=>null,define:()=>{}},
  console, setInterval:()=>42,clearInterval:()=>{},
};
vm.createContext(ctx);
vm.runInContext(source+'\nglobalThis.Panel = IRStudioPanel;',ctx);

(async () => {
  const panel = Object.create(ctx.Panel.prototype);
  const p = {id:'profile1',name:'TCL TV',source:'ir_studio',remote_entity:'remote.test',
    buttons:[{id:'power',name:'Power',status:'pending',verified:false}]};
  panel._selected = ()=>p;
  panel._filter='';
  panel._pending=null;
  panel._pollBusy=false;
  panel._data={profiles:[p]};
  panel._active=p.id;
  panel._language=()=> 'ru';
  panel._remOptions=()=>'<option value="remote.test">Local</option>';
  panel._remotes=()=>[{id:'remote.test'}];
  panel._setHTML=(host,markup)=>{host.html=markup};
  const host={html:''};
  panel.shadowRoot={querySelector:(s)=>s==='#command-list'?host:null};
  panel._toast=()=>{};
  panel._load=async()=>{};
  panel._poll=async()=>{};
  panel._startJobPolling=()=>{};
  panel._renderRows();
  assert(host.html.includes('data-action="learn-modal"'));
  let started;
  panel._call=async(type,args)=>{
    if(type==='start'){started={type,args};return {job_id:'job1'};}
    if(type==='job_cancel')return {status:'cancelling'};
    throw new Error('unexpected RPC '+type);
  };
  await panel._start('learn','power');
  assert.equal(started.args.timeout,60);
  assert.equal(started.args.kind,'learn');
  assert.equal(panel._pending.id,'job1');
  assert(!host.html.includes('data-action="learn-modal"'));
  assert(host.html.includes('data-action="cancel-job"'));
  assert(host.html.includes('class="learn-seconds">60'));
  assert(!source.includes('_showLearnModal('));
  assert(!source.includes('_showWaiting('));
  await panel._cancelLearning();
  assert.equal(panel._pending.cancelling,true);
  assert(host.html.includes('Останавливаем…'));
  assert(!source.includes("this._call('ir_catalog'"));
  assert(!source.includes("this._call('ir_keys'"));
  assert(!source.includes('data-action="account-import"'));
  assert(source.includes('data-action="button-library"'));
  console.log('Learning countdown and cancellation in local-only UI passed.');
})().catch(err=>{console.error(err);process.exitCode=1});
