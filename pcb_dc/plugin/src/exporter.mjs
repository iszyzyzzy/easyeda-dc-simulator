// Read-only EasyEDA API acquisition. No setters, create/delete, IPC or network calls.
export const FORMAT='easyeda-dc-api-snapshot-v1';
const call=(o,k)=>{if(typeof o[k]!=='function')throw new Error(`API unavailable: ${k}`);return o[k]();};
export async function capture(eda,net,stack){
 const s={format:FORMAT,units:'mil',net,stack,primitives:[],physical_holes:[],errors:[],warnings:[],captured_at:new Date().toISOString()};
 const allLayers=await eda.pcb_Layer.getAllLayers();
 s.layers=allLayers.filter(x=>['SIGNAL','PLANE'].includes(x.type)&&x.layerStatus!==0);
 if(!s.layers.length)throw new Error('No copper layers reported');
 if(s.layers.some(x=>![1,2].includes(x.id)))s.errors.push('This prototype only supports an explicitly confirmed two-layer stack.');
 if(typeof eda.pcb_Layer.getCurrentPhysicalStackingConfiguration==='function'){
  try{s.physical_stack_raw=await eda.pcb_Layer.getCurrentPhysicalStackingConfiguration();}catch(e){s.warnings.push('Physical stack API unavailable: '+String(e));}
 }
 const seen=new Set(),seenHoles=new Set();
 async function collect(p,label){
  let id,type;
  try{
   id=call(p,'getState_PrimitiveId');type=call(p,'getState_PrimitiveType');
   if(type==='Component')return;
   if(type==='Poured')return; // Read only through parent Pour.getCopperRegion().
   const key=type+':'+(type==='ComponentPad'?call(p,'getState_ParentComponentPrimitiveId')+':':'')+id;
   // 钻孔与网络无关：先记录物理孔，避免漏掉无网络安装孔或其他网络过孔。
   if(!seenHoles.has(key)&&['Pad','ComponentPad','Via'].includes(type)){
    seenHoles.add(key);
    if(type==='Via')s.physical_holes.push({id:key,type:'Via',x:call(p,'getState_X'),y:call(p,'getState_Y'),diameter:call(p,'getState_HoleDiameter'),via_type:call(p,'getState_ViaType')});
    else{
     const hole=call(p,'getState_Hole');
     if(hole)s.physical_holes.push({id:key,type:'Pad',x:call(p,'getState_X'),y:call(p,'getState_Y'),hole,rotation:call(p,'getState_Rotation'),offset_x:call(p,'getState_HoleOffsetX'),offset_y:call(p,'getState_HoleOffsetY')});
    }
   }
   const n=call(p,'getState_Net');if(n!==net)return;
   if(seen.has(key))return;seen.add(key);
   const r={id:key,type,net:n};
   if(['Pad','ComponentPad'].includes(type)){
    for(const [k,m] of Object.entries({x:'X',y:'Y',layer:'Layer',rotation:'Rotation',pad:'Pad',hole:'Hole',hole_x:'HoleOffsetX',hole_y:'HoleOffsetY',hole_rotation:'HoleRotation',plated:'Metallization',special:'SpecialPad',number:'PadNumber'}))r[k]=call(p,'getState_'+m);
    r.label=label ? `${label}.${r.number}` : `${id}.${r.number}`;
   }else if(['Line','Arc'].includes(type)){
    for(const [k,m] of Object.entries({x1:'StartX',y1:'StartY',x2:'EndX',y2:'EndY',layer:'Layer',width:'LineWidth'}))r[k]=call(p,'getState_'+m);
    if(type==='Arc')r.angle=call(p,'getState_ArcAngle');
   }else if(type==='Pour'){
    r.layer=call(p,'getState_Layer');const region=await call(p,'getCopperRegion');
    if(!region)throw new Error('Missing final copper region; repour in EDA first');
    r.fills=call(region,'getState_PourFills').map(f=>({fill:f.fill,width:f.lineWidth,path:call(f.path,'getSourceStrictComplex')}));
   }else if(type==='Via'){
    for(const [k,m] of Object.entries({x:'X',y:'Y',diameter:'Diameter',drill:'HoleDiameter',via_type:'ViaType',blind_rule:'DesignRuleBlindViaName'}))r[k]=call(p,'getState_'+m);
   }else throw new Error(`Unsupported conductive primitive ${type}`);
   s.primitives.push(r);
  }catch(e){s.errors.push(`${type||'primitive'} ${id||''}: ${String(e)}`);}
 }
 // Explicit getters guard against net-enumeration versions that omit pads/pours.
 for(const c of await eda.pcb_PrimitiveComponent.getAll()){
  const label=call(c,'getState_Designator')||call(c,'getState_PrimitiveId');
  for(const p of await c.getAllPins())await collect(p,label);
 }
 const raw=await eda.pcb_Net.getAllPrimitivesByNet(net);
 for(const p of raw)await collect(p);
 for(const p of await eda.pcb_PrimitiveLine.getAll(net))await collect(p);
 for(const p of await eda.pcb_PrimitiveArc.getAll(net))await collect(p);
 for(const p of await eda.pcb_PrimitivePad.getAll())await collect(p);
 for(const p of await eda.pcb_PrimitivePour.getAll(net))await collect(p);
 for(const p of await eda.pcb_PrimitiveVia.getAll())await collect(p);
 s.warnings.push('API export is experimental. Repour first and compare geometry with EDA. No PCB modification was performed. Do not edit/switch documents while exporting; API snapshots are not atomic.');
 return s;
}
