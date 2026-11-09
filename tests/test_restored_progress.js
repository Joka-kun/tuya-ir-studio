// Regression: imported working commands must not show "0 learned".
//
// The backend deliberately maps restored status=stored/verified to
// needs_check when a different remote driver owns the IR waveform.
// This test reads actual panel.js logic; it never inspects third-party stores.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('custom_components/ir_studio/frontend/panel.js', 'utf8');
const ctx = {
  HTMLElement: class {}, customElements: { get: () => null, define: () => {} },
  console,
};
vm.createContext(ctx);
vm.runInContext(source +
  '\nglobalThis.getProgress = profileLearningSummary;' +
  '\nglobalThis.TestPanel = IRStudioPanel;', ctx);

const progress = (buttons) => ctx.getProgress(buttons);
const restored = [
  { id:'power', status:'needs_check', verified:false, code_in_local_store:null },
  { id:'vol', status:'needs_check', verified:false, code_in_local_store:null },
  { id:'mute', status:'needs_check', verified:false, code_in_local_store:null },
];
const p = progress(restored);
assert.equal(p.total, 3);
assert.equal(p.accounted, 3, 'restored working profiles must not read 0/3');
assert.equal(p.learned, 0, 'do not invent physical verification or cross-store proof');
assert.equal(p.needsCheck, 3, 'keep the explicit verification requirement');

const mixed = progress([
  ...restored,
  {status:'pending', verified:false, code_in_local_store:false},
  {status:'stored', verified:false, code_in_local_store:null},
  {status:'verified', verified:true, code_in_local_store:null},
  {status:'needs_check', verified:false, code_in_local_store:true},
]);
assert.equal(mixed.total, 7);
assert.equal(mixed.learned, 3);
assert.equal(mixed.needsCheck, 3);
assert.equal(mixed.accounted, 6);

assert.equal(progress([]).accounted, 0);
assert.equal(progress([{status:'pending',code_in_local_store:false}]).accounted, 0);
assert.equal(progress([{status:'needs_check',code_in_local_store:false}]).accounted, 1);

const panel = Object.create(ctx.TestPanel.prototype);
const remote = {id:'restored',buttons:restored};
assert.equal(panel._buttonsNeedingLearning(remote).length, 0,
  'unknown foreign CodeStore must prompt verification, not forced retraining');
assert.equal(panel._buttonsNeedingLearning({
  buttons:[
    {status:'pending', verified:false, code_in_local_store:false},
    {status:'needs_check', verified:false, code_in_local_store:false},
  ]
}).length, 2, 'definitely missing codes still need learning');

assert(source.includes('profileLearningSummary(p.buttons)'),
  'sidebar must use the tested summary');
assert(source.includes('${h(summary)}'), 'sidebar must render the calculated summary');
assert(source.includes('обучено/восстановлено'),
  'restored but unverified commands must be labelled distinctly');
console.log('Restored remote counters and guided learning states passed');
