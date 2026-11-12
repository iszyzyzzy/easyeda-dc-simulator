import unittest,copy
try:from api_importer import convert_api_snapshot
except ImportError:from pcb_dc.api_importer import convert_api_snapshot

def fixture():
 return {'format':'easyeda-dc-api-snapshot-v1','units':'mil','net':'VCC','stack':{'confirmed':True,'copper_um':35,'board_mm':1.6,'plating_um':25},'layers':[{'id':1,'name':'Top'},{'id':2,'name':'Bottom'}],'primitives':[],'physical_holes':[]}
def pad(pid,x):return {'id':pid,'type':'ComponentPad','net':'VCC','x':x,'y':50,'layer':1,'rotation':0,'pad':['ELLIPSE',40,40],'hole':None,'number':'1','label':pid}
class APITests(unittest.TestCase):
 def test_api_scale_not_file_scale(self):
  s=fixture();s['primitives']=[{'id':'pour','type':'Pour','net':'VCC','layer':1,'fills':[{'fill':True,'width':0,'path':[[0,0,'L',1000,0,1000,100,0,100]]}]}]
  p=convert_api_snapshot(s);self.assertFalse(p['validation_errors']);self.assertAlmostEqual(max(x for c in p['copper'] for x,y in c['polygon']),25.4)
 def test_lines_arcs(self):
  s=fixture();s['primitives']=[{'id':'line','type':'Line','net':'VCC','layer':1,'x1':0,'y1':0,'x2':100,'y2':0,'width':20},{'id':'arc','type':'Arc','net':'VCC','layer':1,'x1':100,'y1':0,'x2':120,'y2':20,'width':20,'angle':90}]
  p=convert_api_snapshot(s);self.assertFalse(p['validation_errors']);self.assertGreater(len(p['copper']),5)
 def test_through_via_and_hole(self):
  s=fixture();s['primitives']=[{'id':'via','type':'Via','net':'VCC','x':10,'y':20,'diameter':24,'drill':12,'via_type':0}]
  p=convert_api_snapshot(s);self.assertFalse(p['validation_errors']);self.assertEqual(len(p['vias']),1);self.assertEqual(len(p['copper']),2);self.assertTrue(all(c['holes'] for c in p['copper']))
 def test_blind_via_blocked(self):
  s=fixture();s['primitives']=[{'id':'via','type':'Via','net':'VCC','via_type':1}];self.assertTrue(convert_api_snapshot(s)['validation_errors'])
 def test_stack_confirmation(self):
  s=fixture();s['stack']['confirmed']=False;self.assertTrue(convert_api_snapshot(s)['validation_errors'])
 def test_multilayer_blocked(self):
  s=fixture();s['layers'].append({'id':15});self.assertTrue(convert_api_snapshot(s)['validation_errors'])
 def test_unknown_and_missing_pour_blocked(self):
  for typ in ['Fill','Pour']:
   s=fixture();s['primitives']=[{'type':typ,'id':'bad','net':'VCC','layer':1}];self.assertTrue(convert_api_snapshot(s)['validation_errors'])
 def test_api_errors_preserved(self):
  s=fixture();s['errors']=['missing API'];self.assertEqual(convert_api_snapshot(s)['validation_errors'],['missing API'])
 def test_mixed_net_blocked(self):
  s=fixture();r=pad('x',0);r['net']='GND';s['primitives']=[r];self.assertTrue(convert_api_snapshot(s)['validation_errors'])
 def test_pure_trace_solution(self):
  try:from solver import solve
  except ImportError:from pcb_dc.solver import solve
  s=fixture();s['primitives']=[pad('A',0),pad('B',1000),{'type':'Line','id':'trace','net':'VCC','x1':0,'y1':50,'x2':1000,'y2':50,'layer':1,'width':40}]
  p=convert_api_snapshot(s);self.assertFalse(p['validation_errors']);r=solve(p,{'net':'VCC','grid_mm':.1,'source':{'pin':'A:1','voltage_v':5},'loads':[{'pin':'B:1','current_a':1}]});self.assertGreater(r['max_drop_mv'],0)
 def test_no_net_physical_hole(self):
  s=fixture();s['physical_holes']=[{'id':'mount','type':'Pad','x':50,'y':50,'hole':['ROUND',20],'offset_x':0,'offset_y':0,'rotation':0}]
  p=convert_api_snapshot(s);self.assertFalse(p['validation_errors']);self.assertEqual(len(p['drills']),1);self.assertEqual(p['copper'],[]);self.assertEqual(set(p['drills'][0]['layers']),{'1','2'})
 def test_snapshot_without_hole_inventory_blocks(self):
  s=fixture();del s['physical_holes'];self.assertTrue(convert_api_snapshot(s)['validation_errors'])
 def test_api_rounded_rect_not_file_winding(self):
  s=fixture();s['primitives']=[{'id':'p','type':'Pour','net':'VCC','layer':1,'fills':[{'fill':True,'width':0,'path':[['R',0,100,100,100,0,10]]}]}]
  p=convert_api_snapshot(s);self.assertTrue(p['validation_errors']);self.assertEqual(p['copper'],[])
  s['primitives'][0]['fills'][0]['path'][0][-1]=0
  p=convert_api_snapshot(s);self.assertFalse(p['validation_errors']);self.assertEqual(len(p['copper']),1)
 def test_trace_cannot_refill_via_hole(self):
  try:from solver import solve
  except ImportError:from pcb_dc.solver import solve
  s=fixture();s['primitives']=[pad('A',0),pad('B',1000),{'type':'Line','id':'trace','net':'VCC','x1':0,'y1':50,'x2':1000,'y2':50,'layer':1,'width':40},{'type':'Via','id':'v','net':'VCC','x':500,'y':50,'diameter':40,'drill':30,'via_type':0}]
  p=convert_api_snapshot(s);self.assertFalse(p['validation_errors']);config={'net':'VCC','grid_mm':.05,'source':{'pin':'A:1','voltage_v':5},'loads':[{'pin':'B:1','current_a':1}]}
  r=solve(p,config);x=int((500*.0254-r['origin_mm'][0])/.05);y=int((50*.0254-r['origin_mm'][1])/.05)
  top=next(l for l in r['layers'] if l['id']=='1');self.assertIsNone(top['voltage_v'][y][x])
  bad=copy.deepcopy(p);bad['drills']=[];r_bad=solve(bad,config);self.assertGreater(r['max_drop_mv'],r_bad['max_drop_mv'])
if __name__=='__main__':unittest.main()
