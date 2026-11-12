#!/usr/bin/env python3
import argparse,json
from pathlib import Path
from urllib.parse import urlparse,unquote
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from solver import solve
ROOT=Path(__file__).resolve().parent
class Handler(BaseHTTPRequestHandler):
 def reply(self,status,data,kind='application/json'):
  body=json.dumps(data,ensure_ascii=False,allow_nan=False).encode() if kind=='application/json' else data
  self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/api/demo':return self.reply(200,json.loads((ROOT/'examples/demo.json').read_text()))
  if path=='/api/initial':return self.reply(200,self.server.initial)
  if path in ['/','/index.html']:return self.reply(200,(ROOT/'static/index.html').read_bytes(),'text/html')
  self.reply(404,{'error':'Not found'})
 def do_POST(self):
  origin=self.headers.get('Origin')
  if origin and origin!='http://'+self.headers.get('Host',''):return self.reply(403,{'error':'Cross-origin requests denied'})
  try:
   n=int(self.headers.get('Content-Length',0))
   if not 0<n<=40*1024*1024:raise ValueError('Upload must be 1 byte to 40 MiB')
   data=self.rfile.read(n)
   if self.path=='/api/solve':
    req=json.loads(data);return self.reply(200,solve(req['project'],req['config']))
   if self.path=='/api/import':
    name=unquote(self.headers.get('X-Filename','project.json'))
    if name.lower().endswith('.json'):project=json.loads(data)
    else:
     try:from importer import load_project_bytes
     except ImportError:raise ValueError('EPRJ3 adapter unavailable; use intermediate JSON')
     project=load_project_bytes(data,name)
    return self.reply(200,project)
   self.reply(404,{'error':'Not found'})
  except Exception as e:self.reply(400,{'error':str(e)})
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8765);ap.add_argument('--project');args=ap.parse_args();initial=None
 if args.project:
  if args.project.endswith('.json'):initial=json.loads(Path(args.project).read_text())
  else:
   from importer import load_project
   initial=load_project(args.project)
 server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);server.initial=initial
 print(f'PCB DC Lab: http://127.0.0.1:{args.port}',flush=True);server.serve_forever()
