// Browser VM: offline IR file fills already imported button names, not guesses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const src = fs.readFileSync('custom_components/ir_studio/frontend/panel.js', 'utf8');
const ctx = {HTMLElement:class{}, customElements:{get:()=>null,define:()=>{}},
  console, window:{confirm:()=>true}};
vm.createContext(ctx);
vm.runInContext(src + '\nglobalThis.Panel = IRStudioPanel;', ctx);

(async() => {
  const p = {id:'p-tcl',name:'TCL',source:'ir_studio',buttons:[
    {id:'b-on',name:'PowerOn',remote_name:'PowerOn',status:'pending',verified:false},
    {id:'b-v',name:'Volume+',remote_name:'Volume+',status:'stored',verified:true,
     code_in_local_store:true},
  ]};
  const panel = Object.create(ctx.Panel.prototype);
  panel._data = {profiles:[p]};
  panel._active = p.id;
  panel._selected = () => p;
  panel._dialog = html => { panel.html=html };
  panel._dialogClose = () => { panel.closed=true };
  panel._toast = message => {panel.notice=message};
  panel._load = async () => {};
  panel._render = () => {panel.rendered=true};
  const picker = {};
  const mapping = [{dataset:{irBindingSource:'PowerOn'},value:'b-on'}];
  panel.shadowRoot = {
    querySelector:selector => selector==='#ir-profile-file'?picker:null,
    querySelectorAll:selector => selector==='[data-ir-binding-source]'?mapping:[],
  };
  const calls = [];
  panel._call = async(type,params) => {
    calls.push({type,params});
    if(type==='ir_file_preview') return {
      supported_names:['PowerOn','Volume+'],unsupported:[],total:2
    };
    if(type==='ir_file_import') return {
      codes_imported:1,existing_preserved:0,unmapped:1,unsupported:0
    };
    throw Error('Unexpected RPC '+type);
  };
  panel._showIrFileImport();
  assert(panel.html.includes('Выбрать файл'));
  assert(panel.html.includes('Нет такого файла?'));
  assert(!panel.html.includes('Добавить настоящие ИК-коды'));
  assert(panel.html.includes('не перезаписываются'));
  assert(src.includes('data-action="ir-file-open"'));
  assert(src.includes("action==='ir-file-commit'"));

  const fileText = 'Filetype: IR signals file\nVersion: 1\n#\nname: PowerOn\n' +
    'type: raw\nfrequency: 38000\nduty_cycle: 0.33\n' +
    'data: 9000 4500 563 563\n';
  await panel._previewIrFile({name:'TCL.ir',size:fileText.length,text:async()=>fileText});
  assert(panel.html.includes('data-ir-binding-source="PowerOn"'));
  assert(panel.html.includes('selected'));
  assert(panel.html.includes('Volume+'));
  assert(!panel.html.includes('9000'));
  await panel._importIrFileCodes();
  assert(panel.closed);
  assert(panel.rendered);
  assert.equal(calls[1].type,'ir_file_import');
  assert.equal(calls[1].params.profile_id,'p-tcl');
  assert.equal(calls[1].params.content,fileText);
  assert.deepEqual(Array.from(calls[1].params.mappings).map(x=>[x.source_name,x.button_id]),
    [['PowerOn','b-on']]);
  assert.equal(panel._irFileContent,null);

  p.source='tuya_local';
  panel._showIrFileImport();
  assert(panel.notice.includes('нативному Remote'));
  assert.equal(calls.length,2);
  console.log('Offline IR file preview and mapped import browser contract passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
