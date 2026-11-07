// Ensure legacy placeholder cleanup is explicit, selectable and cancellable.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('custom_components/ir_studio/frontend/panel.js','utf8');
let confirms = 0;
const ctx = {
  HTMLElement: class {},
  customElements: {get:()=>null,define:()=>{}},
  window: {confirm:()=>{confirms++;return true;}},
  console,
};
vm.createContext(ctx);
vm.runInContext(source+'\nglobalThis.Panel = IRStudioPanel;',ctx);

(async () => {
  const panel = Object.create(ctx.Panel.prototype);
  const profile = {
    id:'p',name:'Projector',account_ref:'legacy-ref',
    buttons:[
      {id:'unlearned',name:'Power',status:'pending',verified:false,code_in_local_store:false},
      {id:'unknown',name:'Settings',status:'pending',verified:false,code_in_local_store:null},
      {id:'saved',name:'Menu',status:'stored',verified:true,code_in_local_store:true},
    ],
  };
  panel._selected=()=>profile;
  panel._dialog=(html)=>{panel.html=html};
  panel._toast=()=>{};
  panel._dialogClose=()=>{};
  panel._load=async()=>{};
  panel._showReviewUnlearned();
  assert(panel.html.includes('data-cleanup-id="unlearned"'));
  assert(!panel.html.includes('data-cleanup-id="unknown"'));
  assert(!panel.html.includes('data-cleanup-id="saved"'));
  assert(panel.html.includes('Отмена'));
  const calls=[];
  panel._call=async(type,data)=>{calls.push({type,data});return {removed:1,remaining:2,codes_removed:0};};
  panel.shadowRoot={
    querySelector:()=>({querySelectorAll:()=>[{dataset:{cleanupId:'unlearned'}}]})
  };
  await panel._cleanupSelected();
  assert.equal(confirms,1);
  assert.equal(calls.length,1);
  assert.equal(calls[0].type,'profile_remove_unlearned');
  assert.deepEqual(Array.from(calls[0].data.button_ids),['unlearned']);
  console.log('Explicit legacy cleanup modal and code-free selection passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
