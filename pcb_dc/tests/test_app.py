"""Local HTTP smoke test; all server/client calls share one process."""
import sys,json,threading,unittest,urllib.request,urllib.error
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
