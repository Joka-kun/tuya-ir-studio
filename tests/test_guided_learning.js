// Guided IR learning test: Smart Life name-only buttons, local DP202 jobs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const src = fs.readFileSync('custom_components/ir_studio/frontend/panel.js', 'utf8');
const ctx = {
  HTMLElement:class{}, customElements:{get:()=>null,define:()=>{}},
  console, setInterval:()=>42, clearInterval:()=>{},
};
vm.createContext(ctx);
vm.runInContext(src+'\nglobalThis.Panel=IRStudioPanel;',ctx);

(async()=>{
  const p={id:'tcl',name:'TCL',source:'ir_studio',remote_entity:'remote.native',
    buttons:[
      {id:'first',name:'PowerOn',remote_name:'PowerOn',status:'pending',
       verified:false,code_in_local_store:false},
      {id:'already',name:'Volume+',status:'stored',verified:false,
       code_in_local_store:true},
      {id:'second',name:'PowerOff',status:'pending',verified:false,
       code_in_local_store:false},
      {id:'verified',name:'Mute',status:'verified',verified:true,
       code_in_local_store:true},
    ]};
  const panel=Object.create(ctx.Panel.prototype);
  panel._data={profiles:[p]};
  panel._active=p.id;
  panel._filter='';
  panel.shadowRoot={querySelector:()=>null};
  panel._pending=null;
  panel._poller=null;
  panel._pollBusy=false;
  panel._selected=()=>p;
  panel._render=()=>{panel.guide=panel._learningGuide(p)};
  panel._renderRows=()=>{};
  panel._toast=m=>{panel.lastToast=m};
  panel._load=async()=>{};
  panel._startJobPolling=()=>{};
  let status='running', starts=[], cancels=0;
  panel._call=async(type,params)=>{
    if(type==='start'){
      starts.push(params);
      return {job_id:'job'+starts.length};
    }
    if(type==='job') return {status,kind:'learn',message:'No IR'};
    if(type==='job_cancel'){cancels++;status='cancelled';return {status:'cancelling'};}
    throw Error('Unexpected RPC '+type);
  };
  assert.deepEqual(Array.from(panel._buttonsNeedingLearning(p)).map(b=>b.id),
    ['first','second']);
  assert(panel._learningGuide(p).includes('Обучить по порядку (2)'));
  assert(!panel._learningGuide(p).includes('Коды из .ir'));
  await panel._beginBatchLearning();
  assert.deepEqual(starts.map(x=>x.button_id),['first']);
  assert.equal(starts[0].timeout,60);
  assert.equal(panel._pending.buttonId,'first');
  assert.equal(panel._learnWizard.index,0);
  assert(panel.guide.includes('Ожидаем ИК-сигнал'));

  status='done';
  panel._lastPollAt=0;
  await panel._poll();
  assert.equal(panel._pending,null);
  assert.equal(panel._learnWizard.completed,1);
  assert.equal(panel._learnWizard.index,1);
  assert(panel.guide.includes('PowerOff'));
  assert(panel.guide.includes('Продолжить обучение'));
  // No automatic next learn: user must press Continue so signals cannot
  // cross from one physical button into another.
  assert.equal(starts.length,1);

  status='running';
  await panel._batchLearnNext();
  assert.deepEqual(starts.map(x=>x.button_id),['first','second']);
  assert.equal(panel._pending.buttonId,'second');
  // Failed learn does not advance or claim anything was saved.
  status='failed';
  panel._lastPollAt=0;
  await panel._poll();
  assert.equal(panel._learnWizard.completed,1);
  assert.equal(panel._learnWizard.index,1);
  assert(panel.guide.includes('Сигнал не получен'));

  panel._batchLearnSkip();
  assert.equal(panel._learnWizard.skipped,1);
  assert.equal(panel._learnWizard.index,2);
  assert(panel.guide.includes('Обучение завершено'));
  assert(panel.guide.includes('Получено: 1, пропущено: 1'));
  await panel._batchLearnFinish();
  assert.equal(panel._learnWizard,null);
  assert.equal(cancels,0);
  assert.equal(panel._pending,null);

  status='running';
  await panel._beginBatchLearning();
  assert(panel._pending);
  await panel._batchLearnFinish();
  assert.equal(cancels,1);
  assert.equal(panel._learnWizard,null);
  assert.equal(panel._pending,null);

  // All real learned flags suppress the wizard, including verified buttons.
  p.buttons.forEach(b=>{b.code_in_local_store=true;b.status='stored'});
  assert.equal(panel._buttonsNeedingLearning(p).length,0);
  assert.equal(panel._learningGuide(p),'');
  // A slow first call cannot be duplicated by clicking Continue.
  p.buttons[0].code_in_local_store=false;
  p.buttons[0].status='pending';
  let releaseStart;
  const gate=new Promise(resolve=>{releaseStart=resolve;});
  let firstStarts=0;
  panel._call=async type=>{
    if(type==='start'){firstStarts++;await gate;return {job_id:'first-delayed'};}
    if(type==='job')return {status:'running',kind:'learn'};
    throw Error('Unexpected RPC '+type);
  };
  const initial=panel._beginBatchLearning();
  assert.equal(firstStarts,1);
  assert.equal(panel._batchStarting,true);
  assert(panel.guide.includes('Запускаем приём'));
  await panel._batchLearnNext();
  assert.equal(firstStarts,1);
  releaseStart();
  await initial;
  assert.equal(panel._batchStarting,false);
  assert.equal(panel._pending.buttonId,'first');
  console.log('Guided learning: first-click reception, in-flight deduplication and safe sequencing passed');
})().catch(e=>{console.error(e);process.exitCode=1});
