import unittest,tempfile,json,io,zipfile,sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from importer import project_choices,load_project,load_project_bytes,ImportErrorDetail
from app import open_path
BODY='{"type":"DOCHEAD","id":"","ticket":1}||{"docType":"PCB"}|\n'
class FolderTests(unittest.TestCase):
 def make(self,root,name,boards):
  p=root/name;(p/'pcb').mkdir(parents=True);(p/(name+'.eprj3')).write_text('{"format":"folder"}')
  for b in boards:(p/'pcb'/b).write_text(BODY)
  return p
 def test_unicode_multiple_native(self):
  with tempfile.TemporaryDirectory() as t:
   p=self.make(Path(t),'焯 电2',['PCB1.epcb2','PCB1_1.epcb2'])
   self.assertEqual(project_choices(p),['pcb/PCB1.epcb2','pcb/PCB1_1.epcb2'])
   self.assertEqual(open_path(str(p))['pcb_choices'],project_choices(p))
   self.assertIn('copper',load_project(p,'pcb/PCB1_1.epcb2'))
   self.assertEqual(project_choices(p/'焯 电2.eprj3'),project_choices(p))
   with self.assertRaises(ImportErrorDetail):load_project(p)
   with self.assertRaises(ImportErrorDetail):load_project(p,'../PCB1.epcb2')
 def test_parent_projects_no_backup(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.make(root,'工程一',['PCB1.epcb2']);self.make(root,'工程二',['PCB2.epcb2'])
   (root/'backup'/'pcb').mkdir(parents=True);(root/'backup'/'pcb'/'old.epcb2').write_text(BODY)
   self.assertEqual(len(project_choices(root)),2)
 def test_empty_missing(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ImportErrorDetail):load_project(t)
   with self.assertRaises(ImportErrorDetail):open_path(str(Path(t)/'absent'))
 def test_zip_choice(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:
   z.writestr('工程/pcb/PCB1.epcb2',BODY);z.writestr('工程/pcb/PCB2.epcb2',BODY)
  with self.assertRaises(ImportErrorDetail):load_project_bytes(b.getvalue(),'x.zip')
  self.assertIn('pins',load_project_bytes(b.getvalue(),'x.zip','工程/pcb/PCB2.epcb2'))
  with self.assertRaises(ImportErrorDetail):load_project_bytes(b.getvalue(),'x.zip','bad.epcb2')
 def test_symlink_escape(self):
  with tempfile.TemporaryDirectory() as t,tempfile.TemporaryDirectory() as ext:
   root=Path(t);(root/'pcb').mkdir();f=Path(ext)/'secret.epcb2';f.write_text(BODY)
   try:(root/'pcb'/'escape.epcb2').symlink_to(f)
   except OSError:self.skipTest('No symlink support')
   self.assertEqual(project_choices(root),[])

 def test_relative_path(self):
  with tempfile.TemporaryDirectory() as t:
   self.make(Path(t),'project',['PCB1.epcb2']);old=os.getcwd()
   try:
    os.chdir(t)
    self.assertEqual(project_choices('project'),['pcb/PCB1.epcb2'])
    self.assertIn('pins',load_project('project'))
    self.assertIn('pins',load_project('project/pcb/PCB1.epcb2'))
   finally:os.chdir(old)

 def test_oversize_index_checked_before_read(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'large.eprj3'
   with p.open('wb') as f:f.truncate(100_000_001)
   with patch.object(Path,'read_text',side_effect=AssertionError('Must not read oversized index')):
    with self.assertRaisesRegex(ImportErrorDetail,'100 MB'):project_choices(p)
