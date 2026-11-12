"""Local HTTP smoke test; all server/client calls share one process."""
import sys,json,threading,unittest,urllib.request,urllib.error,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Handler,ThreadingHTTPServer
class AppTests(unittest.TestCase):
 def test_http_demo_solve_and_cross_origin(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.initial=None
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   base='http://127.0.0.1:'+str(server.server_port)
   self.assertIn(b'PCB DC Lab',urllib.request.urlopen(base).read())
   p=json.load(urllib.request.urlopen(base+'/api/demo'))
   data=json.dumps({'project':p,'config':{'net':'24V','grid_mm':.5,'source':{'pin':'J1.1','voltage_v':24},'loads':[{'pin':'J2.1','current_a':5}]}}).encode()
   req=urllib.request.Request(base+'/api/solve',data=data,headers={'Content-Type':'application/json'})
   r=json.load(urllib.request.urlopen(req));self.assertAlmostEqual(r['source_current_a'],5,places=6)
   req=urllib.request.Request(base+'/api/solve',data=data,headers={'Origin':'https://evil.example'})
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
   self.assertEqual(e.exception.code,403)
  finally:server.shutdown();server.server_close();thread.join()

 def test_path_selection_and_host_guard(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.initial=None
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   base='http://127.0.0.1:'+str(server.server_port)
   with tempfile.TemporaryDirectory() as t:
    p=Path(t);(p/'pcb').mkdir()
    for name in ('PCB1.epcb2','PCB2.epcb2'):(p/'pcb'/name).write_text('{"type":"DOCHEAD","id":"","ticket":1}||{"docType":"PCB"}|\n')
    def post(payload):return json.load(urllib.request.urlopen(urllib.request.Request(base+'/api/project-path',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})))
    self.assertEqual(post({'path':t})['pcb_choices'],['pcb/PCB1.epcb2','pcb/PCB2.epcb2'])
    self.assertIn('copper',post({'path':t,'board':'pcb/PCB2.epcb2'}))
    with self.assertRaises(urllib.error.HTTPError):post({'path':t,'board':'../bad'})
   req=urllib.request.Request(base+'/api/initial',headers={'Host':'evil.example'})
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
   self.assertEqual(e.exception.code,403)
  finally:server.shutdown();server.server_close();thread.join()
