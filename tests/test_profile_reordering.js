// Sidebar profile ordering: a single drag handle supports pointer and keyboard;
// both persist canonical HA order independently of IR code identities.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source=fs.readFileSync('custom_components/ir_studio/frontend/panel.js','utf8');
const ctx={HTMLElement:class{},customElements:{get:()=>null,define:()=>{}},console};
vm.createContext(ctx);
vm.runInContext(source+'\nglobalThis.Panel=IRStudioPanel;',ctx);

const p = Object.create(ctx.Panel.prototype);
const names=['TV','Projector','Lamp'];
const profiles=names.map((name,i)=>({
  id:'p'+(i+1),name,icon:'tv_standard',
  remote_entity:'remote.hub', remote_device:name,
  buttons:[{id:'power'+i,name:'Power',remote_name:'Power',
    status:'verified',verified:true}],
}));
p._data={profiles,presets:{},jobs:[],icons:[]};
p._hass={locale:{language:'ru-RU'},states:{'remote.hub':{
  state:'off',attributes:{friendly_name:'IR hub'}
}}};
p._active='p2';
p._filter='';
p._setHTML=(_,markup)=>{p.markup=markup};
p._renderRows=()=>{};
p.shadowRoot={querySelector:()=>null,querySelectorAll:()=>[]};
p._remotes=()=>[{id:'remote.hub',name:'Hub',status:'off'}];
const calls=[];
p._doChange=async(type,params)=>{
  calls.push({type,params});
  if(type!=='profile_reorder')throw Error('Unexpected mutation');
  const index=profiles.findIndex(x=>x.id===params.profile_id);
  const moved=profiles.splice(index,1)[0];
  const target=profiles.findIndex(x=>x.id===params.target_profile_id);
  profiles.splice(target+(params.position==='after'?1:0),0,moved);
  return {moved:true};
};

p._render();
assert(p.markup.includes('data-profile-row="p1"'));
assert(p.markup.includes('data-profile-row="p2"'));
assert(p.markup.includes('data-profile-row="p3"'));
assert(p.markup.includes('data-profile-drag="p2"'));
assert.equal((p.markup.match(/data-profile-drag="/g)||[]).length,3);
assert(!p.markup.includes('data-action="profile-move"'));
assert(!p.markup.includes('class="profile-move"'));
assert(p.markup.includes('aria-keyshortcuts="ArrowUp ArrowDown"'));
assert(!p.markup.includes('<button class="profile') || p.markup.includes('class="profile '));

(async()=>{
  assert.equal(await p._moveProfile('p1','up'),false);
  assert.equal(calls.length,0);
  // Arrow keys on the sole visible drag handle work without arrow buttons.
  const keyboardHandle={dataset:{profileDrag:'p3'}};
  let prevented=false;
  await p._handleProfileDragKeydown({
    target:{closest:()=>keyboardHandle},key:'Enter',
    preventDefault(){throw Error('Enter must not be captured');}
  });
  assert.equal(calls.length,0);
  await p._handleProfileDragKeydown({
    target:{closest:()=>keyboardHandle},key:'ArrowUp',
    preventDefault(){prevented=true;}
  });
  assert.equal(prevented,true);
  assert.equal(calls.length,1);
  assert.equal(calls[0].type,'profile_reorder');
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0].params)),{
    profile_id:'p3',target_profile_id:'p2',position:'before'
  });
  assert.deepEqual(profiles.map(x=>x.id),['p1','p3','p2']);
  assert.equal(p._active,'p2');
  assert.equal(p._data.profiles[1].buttons[0].remote_name,'Power');
  assert.equal(await p._moveProfile('p2','down'),false);
  await p._handleProfileDragKeydown({
    target:{closest:()=>({dataset:{profileDrag:'p1'}})},key:'ArrowDown',
    preventDefault(){}
  });
  assert.deepEqual(profiles.map(x=>x.id),['p3','p1','p2']);

  // Pointer drag uses the same backend and does not select/change the profile.
  const classes=()=>({add(){},remove(){}});
  const rows=profiles.map((profile,i)=>({
    dataset:{profileRow:profile.id},classList:classes(),
    getBoundingClientRect:()=>({top:i*50,bottom:(i+1)*50,height:50}),
  }));
  p.shadowRoot.querySelectorAll=selector=>
    selector==='[data-profile-row]'?rows:selector.includes('[data-profile-row]')?rows:[];
  let captured=null;
  const dragged=rows[0];
  const handle={
    hasAttribute:key=>key==='data-profile-drag',
    closest:()=>dragged,
    setPointerCapture:id=>{captured=id},
  };
  p._dragPointerDown({target:{closest:()=>handle},pointerType:'touch',
    button:0,pointerId:5,clientY:25,preventDefault(){}});
  assert.equal(captured,5);
  assert.equal(p._drag.kind,'profile');
  p._dragPointerMove({pointerId:5,clientY:145});
  await p._dragPointerUp({pointerId:5,clientY:145});
  assert.deepEqual(profiles.map(x=>x.id),['p1','p2','p3']);
  assert.equal(p._active,'p2');
  assert.equal(calls.at(-1).type,'profile_reorder');
  assert.deepEqual(JSON.parse(JSON.stringify(calls.at(-1).params)),{
    profile_id:'p3',target_profile_id:'p2',position:'after',
  });

  // A single remote has no meaningless reorder controls.
  p._data.profiles=profiles.slice(0,1);
  p._active=p._data.profiles[0].id;
  p._render();
  assert(!p.markup.includes('data-action="profile-move"'));
  assert(!p.markup.includes('data-profile-drag='));
  console.log('Sidebar profile reorder: single handle, keyboard, drag, bounds, IR identity passed');
})().catch(e=>{console.error(e);process.exitCode=1});
