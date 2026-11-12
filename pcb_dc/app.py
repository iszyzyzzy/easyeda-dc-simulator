#!/usr/bin/env python3
import argparse,json
from pathlib import Path
from urllib.parse import urlparse,unquote
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from solver import solve
ROOT=Path(__file__).resolve().parent
def import_json(data):
 if data.get('format')=='easyeda-dc-api-snapshot-v1':
  from api_importer import convert_api_snapshot
  return convert_api_snapshot(data)
 return data
def open_path(path,board=None):
 from importer import project_choices,load_project,archive_choices
 p=Path(path).expanduser();choices=project_choices(p)
 if not choices and p.is_file():
  if p.stat().st_size>100_000_000:raise ValueError('Project file larger than 100 MB')
  choices=archive_choices(p.read_bytes())
 if board is None and len(choices)>1:return {'pcb_choices':choices,'project_path':str(p)}
 return import_json(load_project(p,board))
class Handler(BaseHTTPRequestHandler):
 def local_host(self):
  # Reject DNS-rebinding hosts before exposing local path reads.
  return self.headers.get('Host','').split(':')[0].lower() in ('127.0.0.1','localhost')

 def reply(self,status,data,kind='application/json'):
  body=json.dumps(data,ensure_ascii=False,allow_nan=False).encode() if kind=='application/json' else data
  self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if not self.local_host():return self.reply(403,{'error':'Localhost Host header required'})
  path=urlparse(self.path).path
  if path=='/api/demo':return self.reply(200,json.loads((ROOT/'examples/demo.json').read_text()))
  if path=='/api/initial':return self.reply(200,self.server.initial)
  if path in ['/','/index.html']:return self.reply(200,(ROOT/'static/index.html').read_bytes(),'text/html')
  self.reply(404,{'error':'Not found'})
 def do_POST(self):
  if not self.local_host():return self.reply(403,{'error':'Localhost Host header required'})
  origin=self.headers.get('Origin')
  if origin and origin!='http://'+self.headers.get('Host',''):return self.reply(403,{'error':'Cross-origin requests denied'})
  try:
   n=int(self.headers.get('Content-Length',0))
   if not 0<n<=40*1024*1024:raise ValueError('Upload must be 1 byte to 40 MiB')
   data=self.rfile.read(n)
   if self.path=='/api/project-path':
    req=json.loads(data);return self.reply(200,open_path(req['path'],req.get('board')))
   if self.path=='/api/solve':
    req=json.loads(data);return self.reply(200,solve(req['project'],req['config']))
   if self.path=='/api/import':
    name=unquote(self.headers.get('X-Filename','project.json'))
    if name.lower().endswith('.json'):project=import_json(json.loads(data))
    else:
     try:from importer import load_project_bytes,archive_choices
     except ImportError:raise ValueError('EPRJ3 adapter unavailable; use intermediate JSON')
     choices=archive_choices(data);board=unquote(self.headers.get('X-PCB','')) or None
     if board is None and len(choices)>1:return self.reply(200,{'pcb_choices':choices})
     project=load_project_bytes(data,name,board)
    return self.reply(200,project)
   self.reply(404,{'error':'Not found'})
  except Exception as e:self.reply(400,{'error':str(e)})
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8765);ap.add_argument('--project');ap.add_argument('--pcb',help='Relative PCB path when a project has multiple boards');args=ap.parse_args();initial=None
 if args.project:
  if args.project.endswith('.json'):initial=import_json(json.loads(Path(args.project).read_text()))
  else:
   initial=open_path(args.project,args.pcb)
 server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);server.initial=initial
 print(f'PCB DC Lab: http://127.0.0.1:{args.port}',flush=True);server.serve_forever()
