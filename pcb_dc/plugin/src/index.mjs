import {capture} from './exporter.mjs';
function info(s){eda.sys_Dialog.showInformationMessage(s,'PCB DC Lab');}
export async function exportNetwork(){
 try{
  const nets=await eda.pcb_Net.getAllNetsName();
  eda.sys_Dialog.showSelectDialog(nets,'先手动重新铺铜。选择导出的网络。','只读导出，不修改 PCB。','PCB DC Lab',undefined,false,async net=>{
   eda.sys_Dialog.showInputDialog('请输入均匀铜厚(µm),板厚(mm),孔铜厚(µm)，例如 35,1.6,25。仅支持双层板，数值必须与实际板相符。','仅支持双层板；不会自动假定实际叠层。','确认物理参数','text','35,1.6,25',undefined,async value=>{
    try{
     const v=value.split(',').map(Number);if(v.length!==3||v.some(x=>!Number.isFinite(x)||x<=0))throw new Error('Invalid physical dimensions');
     const s=await capture(eda,net,{confirmed:true,copper_um:v[0],board_mm:v[1],plating_um:v[2]});
     await eda.sys_FileSystem.saveFile(new Blob([JSON.stringify(s,null,2)],{type:'application/json'}),'pcb-dc-api.json');
     info(s.errors.length?`已导出，但有 ${s.errors.length} 个阻断问题，请在求解器查看。`:'已导出。到本地 PCB DC Lab 导入 JSON，再选择电源和负载端子。');
    }catch(e){info(String(e));}
   });
  });
 }catch(e){info(String(e));}
}
