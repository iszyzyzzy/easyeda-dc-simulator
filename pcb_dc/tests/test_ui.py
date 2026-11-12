import unittest,subprocess,shutil
from pathlib import Path
class UITests(unittest.TestCase):
 def test_initial_response_does_not_override_new_selection(self):
  if not shutil.which('node'):self.skipTest('Node not installed')
  source=(Path(__file__).resolve().parents[1]/'static/index.html').read_text()
  function='async function initializeProject'+source.split('async function initializeProject',1)[1].split('initializeProject();',1)[0]
  script="""
let importEpoch=0,events=[],elements={projectpath:{},error:{},demo:{click(){events.push('demo')}}};
const $=x=>elements[x],setProject=x=>events.push(x),chooseBoard=(...x)=>events.push(x),api=()=>{};
let release;const fetch=()=>new Promise(resolve=>release=resolve);
"""+function+"""
(async()=>{
 for(const value of [null,{name:'old'},{pcb_choices:['old'],project_path:'old'}]){
  let done=initializeProject();importEpoch++;release({json:async()=>value});await done;
  if(events.length||elements.projectpath.value)throw Error('Stale initial overwrote selection');
 }
 let done=initializeProject();importEpoch++;release({json:async()=>{throw Error('stale')}});await done;
 if(elements.error.textContent)throw Error('Stale error overwrote selection');
 done=initializeProject();release({json:async()=>({name:'initial'})});await done;
 if(events.length!==1||events[0].name!=='initial')throw Error('Valid initial not applied');
})().catch(e=>{console.error(e);process.exit(1)});
"""
  subprocess.run(['node','-e',script],check=True,capture_output=True,text=True)
