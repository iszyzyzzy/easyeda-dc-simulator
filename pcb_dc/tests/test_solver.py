import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solver import solve,RHO

def board():
 return {'units':'mm','layers':[{'id':'1','thickness_um':35}], 'copper':[{'net':'V','layer':'1','polygon':[[0,0],[10,0],[10,1],[0,1]]}], 'pins':[{'id':'S','net':'V','layer':'1','x':.25,'y':.5,'radius_mm':.3},{'id':'L','net':'V','layer':'1','x':9.75,'y':.5,'radius_mm':.3}], 'vias':[]}
def cfg():return {'net':'V','grid_mm':.5,'source':{'pin':'S','voltage_v':1},'loads':[{'pin':'L','current_a':1}]}
class SolverTests(unittest.TestCase):
 def test_strip_analytic(self):
  r=solve(board(),cfg());expected=RHO*.0095/(35e-6*.001)
  self.assertAlmostEqual(r['max_drop_mv']/1000,expected,places=10);self.assertAlmostEqual(r['total_loss_w'],expected,places=10);self.assertAlmostEqual(r['source_current_a'],1,places=10)
 def test_scaling(self):
  c=cfg();r=solve(board(),c);c['loads'][0]['current_a']=2;s=solve(board(),c)
  self.assertAlmostEqual(s['max_drop_mv'],r['max_drop_mv']*2,places=8);self.assertAlmostEqual(s['total_loss_w'],r['total_loss_w']*4,places=8)
 def test_disconnected(self):
  p=board();p['copper'][0]['holes']=[[[4,0],[6,0],[6,1],[4,1]]]
  with self.assertRaisesRegex(ValueError,'Disconnected'):solve(p,cfg())
 def test_overlap(self):
  c=cfg();c['loads'][0]['pin']='S'
  with self.assertRaisesRegex(ValueError,'overlap'):solve(board(),c)
 def test_huge_mesh(self):
  c=cfg();c['grid_mm']=.001
  with self.assertRaisesRegex(ValueError,'Mesh too large'):solve(board(),c)
 def test_via(self):
  p=board();p['layers'].append({'id':'2','thickness_um':35});c=copy.deepcopy(p['copper'][0]);c['layer']='2';p['copper'].append(c);p['pins'][1]['layer']='2';p['vias']=[{'net':'V','x':5.25,'y':.25,'diameter_mm':.4,'drill_mm':.2,'plating_um':25,'length_mm':1.6,'layers':['1','2']}]
  c=cfg();c['grid_mm']=.1
  r=solve(p,c);self.assertGreater(r['via_loss_w'],0);self.assertAlmostEqual(r['source_current_a'],1,places=8)
  for layer in r['layers']:self.assertIsNone(layer['voltage_v'][2][52])
 def test_trace_crossing_drill(self):
  p=board();p['copper'][0]['holes']=[[[4,0],[6,0],[6,1],[4,1]]]
  p['copper'].append({'net':'V','layer':'1','polygon':[[3,0],[7,0],[7,1],[3,1]]})
  # 铺铜避让内允许独立走线；物理钻孔则必须切断这条走线。
  self.assertGreater(solve(p,cfg())['total_loss_w'],0)
  p['drills']=[{'layers':['1'],'polygon':[[4.5,0],[5.5,0],[5.5,1],[4.5,1]]}]
  with self.assertRaisesRegex(ValueError,'Disconnected'):solve(p,cfg())
 def test_legacy_via_drill_affects_other_nets(self):
  p=board();p['vias']=[{'net':'OTHER','x':5,'y':.5,'drill_mm':1.5,'layers':['1','2']}]
  with self.assertRaisesRegex(ValueError,'Disconnected'):solve(p,cfg())
 def test_explicit_drill_contours_are_authoritative(self):
  p=board();p['vias']=[{'net':'OTHER','x':5,'y':.5,'drill_mm':1.5,'layers':['1','2']}]
  p['drills']=[{'layers':['2'],'polygon':[[4,0],[6,0],[6,1],[4,1]]}]
  self.assertGreater(solve(p,cfg())['total_loss_w'],0)
 def test_thermal(self):
  c=cfg();c['thermal_resistance_k_w']=10;r=solve(board(),c);self.assertAlmostEqual(r['estimated_temperature_rise_k'],r['total_loss_w']*10)
 def test_bad_import(self):
  p=board();p['validation_errors']=['missing pour']
  with self.assertRaisesRegex(ValueError,'Import incomplete'):solve(p,cfg())
 def test_net_scoped_import(self):
  p=board();p['validation_errors_by_net']={'OTHER':['unsupported via']}
  self.assertGreater(solve(p,cfg())['total_loss_w'],0)
  p['validation_errors_by_net']['V']=['unsupported via']
  with self.assertRaisesRegex(ValueError,'Import incomplete for V'):solve(p,cfg())
 def test_bad_temperature(self):
  c=cfg();c['copper_temperature_c']=-1000
  with self.assertRaises(ValueError):solve(board(),c)
 def test_floating(self):
  p=board();p['copper'].append({'net':'V','layer':'1','polygon':[[20,0],[21,0],[21,1],[20,1]]});r=solve(p,cfg());self.assertTrue(any('floating' in w for w in r['warnings']))
if __name__=='__main__':unittest.main()
