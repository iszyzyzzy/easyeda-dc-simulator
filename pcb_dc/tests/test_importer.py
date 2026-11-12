import unittest,json,math,io,zipfile
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from importer import *
def rec(t,i,v,ticket=1):return json.dumps({'type':t,'id':i,'ticket':ticket})+'||'+(json.dumps(v) if v is not None else '')+'|\n'
class ImporterTests(unittest.TestCase):
 def test_arc(self):
  p=arc_points([1,0],[0,1],90);self.assertAlmostEqual(p[-1][0],0);self.assertAlmostEqual(p[-1][1],1)
 def test_rect(self):self.assertEqual(path_points(['R',0,10,20,10,0]),[[0,10],[20,10],[20,0],[0,0]])
 def test_bottom(self):self.assertEqual(transform([[2,3]],10,20,0,True),[[12,17]])
 def test_scale_holes(self):
  s=rec('DOCHEAD','',{'docType':'PCB'})+rec('POUR','p',{'netName':'GND','layerId':1})+rec('POURED','["POURED","p"]',{'pourFill':[{'fill':True,'path':[['R',0,10,20,10,0],['CIRCLE',5,5,1]]}]})
  d=convert(s);self.assertAlmostEqual(d['copper'][0]['polygon'][1][0],5.08);self.assertEqual(len(d['copper'][0]['holes']),1);self.assertEqual(d['validation_errors'],[])
 def test_missing_pour_blocks(self):
  s=rec('DOCHEAD','',{'docType':'PCB'})+rec('POUR','p',{'netName':'GND','layerId':1,'path':[['R',0,0,20,10,0]]})
  d=convert(s);self.assertEqual(d['copper'],[]);self.assertTrue(d['validation_errors_by_net'].get('GND'))
 def test_via_blocks(self):
  d=convert(rec('DOCHEAD','',{'docType':'PCB'})+rec('VIA','v',{'netName':'GND'}));self.assertTrue(d['validation_errors']);self.assertIn('physical drill span',d['validation_errors'][0])
 def test_delete(self):
  d=records(rec('DOCHEAD','',{'docType':'PCB'})+rec('LINE','a',{'x':2})+rec('LINE','a',None,2));self.assertIsNone(d[0]['records'][('LINE','a')][1])
 def test_index_rejected(self):
  with self.assertRaises(ImportErrorDetail):load_project_bytes(b'{}','x.eprj3')
 def test_footprint_mapping(self):
  s=rec('DOCHEAD','',{'docType':'FOOTPRINT','uuid':'fp'})+rec('PAD','p',{'centerX':10,'centerY':20,'layerId':1,'num':'1','defaultPad':{'padType':'RECT','width':10,'height':10}})+rec('DOCHEAD','',{'docType':'PCB'})+rec('COMPONENT','c',{'x':100,'y':200,'angle':0,'layerId':2})+rec('ATTR','f',{'parentId':'c','key':'Footprint','value':'fp'})+rec('ATTR','r',{'parentId':'c','key':'Designator','value':'J1'})+rec('PAD_NET','["PAD_NET","c","1","p"]',{'padNet':'VCC'})
  d=convert(s);self.assertEqual(d['validation_errors'],[]);p=d['pins'][0];self.assertEqual(p['layer'],'2');self.assertAlmostEqual(p['x'],110*MIL);self.assertAlmostEqual(p['y'],180*MIL);self.assertEqual(p['label'],'J1.1')
 def test_disjoint_outer_contours(self):
  a=[[0,0],[10,0],[10,10],[0,10]];b=[[20,0],[30,0],[30,10],[20,10]]
  self.assertEqual(len(nonzero_regions([a,b])),2)
 def test_nonzero_same_winding_is_not_hole(self):
  a=[[0,0],[10,0],[10,10],[0,10]];b=[[2,2],[8,2],[8,8],[2,8]]
  regions=nonzero_regions([a,b]);self.assertEqual(len(regions),1);self.assertEqual(regions[0][1],[])
 def test_nonzero_hole_and_nested_island(self):
  a=[[0,0],[10,0],[10,10],[0,10]];b=[[2,2],[2,8],[8,8],[8,2]];c=[[3,3],[7,3],[7,7],[3,7]]
  regions=nonzero_regions([a,b,c]);self.assertEqual(len(regions),2);self.assertEqual(len(regions[0][1]),1)
 def test_crossing_contours_rejected(self):
  a=[[0,0],[10,0],[10,10],[0,10]];b=[[5,5],[15,5],[15,15],[5,15]]
  with self.assertRaises(ImportErrorDetail):nonzero_regions([a,b])
 def test_ellipse_ambiguity_blocks(self):
  s=rec('DOCHEAD','',{'docType':'PCB'})+rec('PAD','p',{'centerX':0,'centerY':0,'layerId':1,'num':'1','netName':'VCC','defaultPad':{'padType':'ELLIPSE','width':10,'height':20}})
  d=convert(s);self.assertTrue(d['validation_errors']);self.assertEqual(d['copper'],[])
 def test_winding_flags(self):
  self.assertEqual(path_points(['R',0,10,20,10,0,1]),list(reversed(path_points(['R',0,10,20,10,0,0]))))
  self.assertEqual(path_points(['CIRCLE',0,0,1,0]),list(reversed(path_points(['CIRCLE',0,0,1,1]))))
 def test_zip(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:z.writestr('pcb/a.epcb2',rec('DOCHEAD','',{'docType':'PCB'}))
  self.assertEqual(load_project_bytes(b.getvalue(),'x.zip')['units'],'mm')
 def test_zip_eprj3_extension_bytes_and_path(self):
  import tempfile
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:z.writestr('pcb/a.epcb2',rec('DOCHEAD','',{'docType':'PCB'}))
  self.assertEqual(load_project_bytes(b.getvalue(),'x.eprj3')['units'],'mm')
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.eprj3';p.write_bytes(b.getvalue())
   self.assertEqual(load_project(p)['units'],'mm')
 def test_folder_index_path_and_upload_message(self):
  import tempfile
  data=b'{"format":"folder"}'
  with self.assertRaisesRegex(ImportErrorDetail,'folder-format project index'):load_project_bytes(data,'x.eprj3')
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.eprj3';p.write_bytes(data);(p.parent/'pcb').mkdir()
   (p.parent/'pcb'/'a.epcb2').write_text(rec('DOCHEAD','',{'docType':'PCB'}))
   self.assertEqual(load_project(p)['units'],'mm')
 def test_unknown_eprj3_not_claimed_incomplete(self):
  with self.assertRaisesRegex(ImportErrorDetail,'Unrecognised standalone'):load_project_bytes(b'unknown data','x.eprj3')
 def test_no_net_npth_preserved(self):
  s=rec('DOCHEAD','',{'docType':'PCB'})+rec('PAD','mount',{'centerX':50,'centerY':60,'layerId':12,'hole':['ROUND',20,20]})
  d=convert(s);self.assertFalse(d['validation_errors']);self.assertEqual(len(d['drills']),1);self.assertEqual(d['pins'],[]);self.assertEqual(set(d['drills'][0]['layers']),{'1','2'});self.assertAlmostEqual(max(x for x,y in d['drills'][0]['polygon']),60*MIL)
 def test_pth_preserved_as_physical_hole(self):
  s=rec('DOCHEAD','',{'docType':'PCB'})+rec('PAD','pth',{'centerX':0,'centerY':0,'layerId':12,'netName':'VCC','defaultPad':['ELLIPSE',40,40],'hole':['ROUND',20,20],'plated':True})
  d=convert(s);self.assertFalse(d['validation_errors']);self.assertEqual(len(d['drills']),1);self.assertEqual(len(d['vias']),1)
if __name__=='__main__':unittest.main()
