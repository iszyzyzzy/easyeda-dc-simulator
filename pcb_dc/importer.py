"""Experimental read-only EPRJ3 importer. Unsupported geometry blocks solving.
Independent implementation based on official easyeda file-format/viewer docs.
PCB coordinates are mil, except POURED.pourFill at 0.1 PCB scale.
"""
import json, math, io, zipfile
from pathlib import Path
MIL=0.0254
class ImportErrorDetail(ValueError): pass

def transform(points,x=0,y=0,angle=0,mirror=False):
 c=math.cos(math.radians(angle));s=math.sin(math.radians(angle))
 return [[x+px*c-(-py if mirror else py)*s,y+px*s+(-py if mirror else py)*c] for px,py in points]
def circle(x,y,r,n=48):return [[x+r*math.cos(i*math.tau/n),y+r*math.sin(i*math.tau/n)] for i in range(n)]
def arc_points(start,end,angle):
 a=math.radians(angle);dx=end[0]-start[0];dy=end[1]-start[1]
 if abs(a)<1e-10:return [list(end)]
 if abs(math.sin(a/2))<1e-9:raise ImportErrorDetail('Full circle ARC unsupported; use CIRCLE')
 cx=(start[0]+end[0])/2-dy/(2*math.tan(a/2));cy=(start[1]+end[1])/2+dx/(2*math.tan(a/2))
 t=math.atan2(start[1]-cy,start[0]-cx);r=math.hypot(start[0]-cx,start[1]-cy);n=max(2,math.ceil(abs(angle)/4))
 return [[cx+r*math.cos(t+a*i/n),cy+r*math.sin(t+a*i/n)] for i in range(1,n+1)]
def path_points(p):
 if not p:raise ImportErrorDetail('Empty path')
 if p[0]=='CIRCLE':
  pts=circle(p[1],p[2],p[3],96)
  return pts if len(p)<5 or p[4] else list(reversed(pts))
 if p[0]=='R':
  _,x,y,w,h,a,*rest=p
  if len(rest)>1 and rest[1]:raise ImportErrorDetail('Rounded R path unsupported')
  pts=transform([[0,0],[w,0],[w,-h],[0,-h]],x,y,a)
  return list(reversed(pts)) if rest and rest[0] else pts
 if isinstance(p[0],list):return p
 pts=[[float(p[0]),float(p[1])]];i=2;mode='L'
 while i<len(p):
  if isinstance(p[i],str):mode=p[i];i+=1;continue
  if mode=='L':pts.append([p[i],p[i+1]]);i+=2
  elif mode in ('ARC','CARC'):pts.extend(arc_points(pts[-1],p[i+1:i+3],p[i]));i+=3;mode='L'
  elif mode=='C':
   a=pts[-1];b=p[i:i+2];c=p[i+2:i+4];d=p[i+4:i+6]
   for j in range(1,33):
    t=j/32;u=1-t;pts.append([u**3*a[k]+3*u*u*t*b[k]+3*u*t*t*c[k]+t**3*d[k] for k in (0,1)])
   i+=6
  else:raise ImportErrorDetail('Unknown path opcode '+mode)
 return pts
def stroke_parts(points,width,closed=False):
 if width<=0:return []
 r=width/2;out=[circle(x,y,r,24) for x,y in points]
 for a,b in zip(points,points[1:]+points[:1] if closed else points[1:]):
  dx=b[0]-a[0];dy=b[1]-a[1];n=math.hypot(dx,dy)
  if n:
   nx=-dy/n*r;ny=dx/n*r;out.append([[a[0]+nx,a[1]+ny],[b[0]+nx,b[1]+ny],[b[0]-nx,b[1]-ny],[a[0]-nx,a[1]-ny]])
 return out

def nonzero_regions(raw_rings):
 """Convert disjoint/nested simple contours using nonzero winding, not even-odd.
 Crossings/touching/degenerate rings are rejected rather than guessing topology.
 """
 rings=[]
 for raw in raw_rings:
  ring=[]
  for p in raw:
   if not ring or math.dist(p,ring[-1])>1e-9:ring.append(p)
  if len(ring)>1 and math.dist(ring[0],ring[-1])<1e-9:ring.pop()
  if len(ring)<3:raise ImportErrorDetail('Degenerate filled contour')
  rings.append(ring)
 if sum(map(len,rings))>10000:raise ImportErrorDetail('Contour topology exceeds prototype verification limit')
 def area(p):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))/2
 areas=[area(p) for p in rings]
 if any(abs(a)<1e-10 for a in areas):raise ImportErrorDetail('Zero-area filled contour')
 def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 def intersects(a,b,c,d):
  eps=1e-9
  if max(a[0],b[0])+eps<min(c[0],d[0]) or max(c[0],d[0])+eps<min(a[0],b[0]) or max(a[1],b[1])+eps<min(c[1],d[1]) or max(c[1],d[1])+eps<min(a[1],b[1]):return False
  u=cross(a,b,c);v=cross(a,b,d);w=cross(c,d,a);z=cross(c,d,b)
  return ((u>=-eps and v<=eps) or (v>=-eps and u<=eps)) and ((w>=-eps and z<=eps) or (z>=-eps and w<=eps))
 edges=[list(zip(p,p[1:]+p[:1])) for p in rings]
 for i,ee in enumerate(edges):
  for j,(a,b) in enumerate(ee):
   for k in range(j+1,len(ee)):
    if k==j+1 or (j==0 and k==len(ee)-1):continue
    if intersects(a,b,*ee[k]):raise ImportErrorDetail('Self-intersecting filled contour unsupported')
  for other in edges[i+1:]:
   if any(intersects(a,b,c,d) for a,b in ee for c,d in other):raise ImportErrorDetail('Crossing or touching filled contours unsupported')
 def inside(p,poly):
  x,y=p;result=False
  for a,b in zip(poly,poly[1:]+poly[:1]):
   if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:result=not result
  return result
 parent=[]
 for i,p in enumerate(rings):
  containers=[j for j,q in enumerate(rings) if j!=i and inside(p[0],q)]
  parent.append(min(containers,key=lambda j:abs(areas[j])) if containers else None)
 def ancestors(i):
  seen=set();j=parent[i]
  while j is not None:
   if j in seen:raise ImportErrorDetail('Inconsistent contour containment')
   seen.add(j);yield j;j=parent[j]
 signs=[1 if a>0 else -1 for a in areas];starts={};holes=[]
 for i in range(len(rings)):
  before=sum(signs[j] for j in ancestors(i));after=before+signs[i]
  if before==0 and after!=0:starts[i]=[rings[i],[]]
  elif before!=0 and after==0:holes.append(i)
 for i in holes:
  owner=next((j for j in ancestors(i) if j in starts),None)
  if owner is None:raise ImportErrorDetail('Hole has no filled parent')
  starts[owner][1].append(rings[i])
 return list(starts.values())

def records(text):
 docs=[];doc=None
 for lineno,line in enumerate(text.splitlines(),1):
  if not line.strip():continue
  if '||' not in line:raise ImportErrorDetail(f'Invalid record line {lineno}')
  a,b=line.split('||',1);head=json.loads(a);body=b[:-1] if b.endswith('|') else b
  if head.get('type')=='DOCHEAD':doc={'head':json.loads(body),'records':{}};docs.append(doc);continue
  if doc is None:raise ImportErrorDetail('Missing DOCHEAD')
  key=(head.get('type'),str(head.get('id','')));ticket=head.get('ticket',0);old=doc['records'].get(key)
  if old and old[0]>ticket:continue
  doc['records'][key]=(ticket,json.loads(body) if body else None)
 return docs

def keyparts(s):
 try:return json.loads(s) if s.startswith('[') else []
 except ValueError:return []

def convert(text,name='PCB'):
 docs=records(text);pcbs=[d for d in docs if d['head'].get('docType')=='PCB']
 if len(pcbs)!=1:raise ImportErrorDetail(f'Expected one PCB document, found {len(pcbs)}')
 rr={(t,i):v for (t,i),(_,v) in pcbs[0]['records'].items() if v is not None}
 bytype=lambda typ:[(i,v) for (t,i),v in rr.items() if t==typ]
 out={'units':'mm','name':name,'layers':[],'copper':[],'pins':[],'vias':[],'drills':[],'warnings':[],'validation_errors':[],'validation_errors_by_net':{}}
 def warn(s):
  if s not in out['warnings']:out['warnings'].append(s)
 def error(s,net=None):
  target=out['validation_errors_by_net'].setdefault(str(net),[]) if net else out['validation_errors']
  if s not in target:target.append(s)
 phys={keyparts(i)[1]:v for i,v in bytype('LAYER_PHYS') if len(keyparts(i))>1}
 for i,v in bytype('LAYER'):
  lid=v.get('layerId');typ=v.get('layerType','')
  if v.get('use',True) and (lid in (1,2) or typ in ('TOP','BOTTOM','SIGNAL','INNER','PLANE')):
   th=phys.get(lid,{}).get('thickness',0)*25.4
   if not th:th=35;warn('Copper thickness missing: 35 um assumed; verify fabrication stackup.')
   out['layers'].append({'id':str(lid),'name':v.get('layerName',str(lid)),'thickness_um':th})
 if not out['layers']:
  out['layers']=[{'id':'1','name':'Top','thickness_um':35},{'id':'2','name':'Bottom','thickness_um':35}];warn('Missing layer stackup: two copper layers at 35 um assumed.')
 lids=[l['id'] for l in out['layers']];total=sum(v.get('thickness',0)*MIL for v in phys.values()) or 1.6
 def add(net,layer,polygon,holes=None,scale=MIL):
  if not net or str(layer) not in lids or len(polygon)<3:return
  out['copper'].append({'net':str(net),'layer':str(layer),'polygon':[[x*scale,y*scale] for x,y in polygon],'holes':[[[x*scale,y*scale] for x,y in h] for h in holes or []]})
 def shape(net,layer,paths,width=0,fill=True,scale=MIL):
  if not paths:return
  if not isinstance(paths[0],list):paths=[paths]
  rings=[path_points(p) for p in paths]
  if fill:
   for outer,holes in nonzero_regions(rings):add(net,layer,outer,holes,scale)
  if width:
   for ring in rings:
    for poly in stroke_parts(ring,width,fill):add(net,layer,poly,scale=scale)
 pours=dict(bytype('POUR'));seen=set()
 for i,v in bytype('POURED'):
  parts=keyparts(i);target=v.get('targetId') or (parts[1] if len(parts)>1 else None);parent=pours.get(target)
  if not parent:error('POURED parent not found: '+str(target));continue
  seen.add(target);fills=v.get('pourFill');scale=MIL*10 if fills is not None else MIL
  for f in fills if fills is not None else [v]:
   try:shape(parent.get('netName'),parent.get('layerId'),f.get('path'),f.get('strokeWidth',0),f.get('fill',True),scale)
   except (ValueError,TypeError,IndexError,KeyError) as e:error(f'Unsupported POURED {target}: {e}',parent.get('netName'))
 for pid in pours.keys()-seen:error('Missing final POURED: '+pid+'. Repour and save in EDA. Boundary excluded.',pours[pid].get('netName'))
 for typ in ('LINE','ARC','CARC','POLY','FILL','TEARDROP'):
  for i,v in bytype(typ):
   if not v.get('netName') or str(v.get('layerId')) not in lids:continue
   try:
    if typ=='LINE':pts=[[v['startX'],v['startY']],[v['endX'],v['endY']]]
    elif typ in ('ARC','CARC'):pts=[[v['startX'],v['startY']]]+arc_points([v['startX'],v['startY']],[v['endX'],v['endY']],v['angle'])
    else:
     if typ=='FILL' and v.get('fillStyle',0) not in (0,'SOLID'):raise ImportErrorDetail('Non-solid FILL')
     shape(v['netName'],v['layerId'],v['path'],v.get('width',0),typ in ('FILL','TEARDROP'));continue
    for poly in stroke_parts(pts,v['width']):add(v['netName'],v['layerId'],poly)
   except (ValueError,TypeError,IndexError,KeyError) as e:error(f'Unsupported {typ} {i}: {e}',v.get('netName'))
 attrs={}
 for i,v in bytype('ATTR'):attrs.setdefault(v.get('parentId'),{})[v.get('key')]=v.get('value')
 footprints={d['head'].get('uuid'):d for d in docs if d['head'].get('docType')=='FOOTPRINT'}
 mappings={}
 for i,v in bytype('PAD_NET'):
  p=keyparts(i)
  if len(p)>=4:mappings[(p[1],p[2],p[3])]=v.get('padNet','')
  else:mappings[(i,v.get('padNum'),v.get('padId'))]=v.get('padNet','')
 def pad(pid,v,component=None,compid=None):
  comp=component or {};bottom=comp.get('layerId')==2;x=v.get('centerX',0);y=v.get('centerY',0);num=str(v.get('num',''));net=v.get('netName','')
  if compid:net=mappings.get((compid,num,pid),mappings.get((compid,num,None),net))
  # 物理钻孔独立于网络，必须在无网络焊盘提前返回前保留下来。
  raw_hole=v.get('hole')
  if raw_hole:
   raw_hole=raw_hole if isinstance(raw_hole,dict) else dict(zip(['holeType','width','height'],raw_hole))
   d=raw_hole.get('width',0)
   if raw_hole.get('holeType') not in ('ROUND','CIRCLE') or d!=raw_hole.get('height') or d<=0:raise ImportErrorDetail('Unsupported physical drill geometry')
   hole_poly=transform(circle(v.get('padOffsetX',0),v.get('padOffsetY',0),d/2),x,y,v.get('padAngle',0))
   hole_poly=transform(hole_poly,comp.get('x',comp.get('positionX',0)),comp.get('y',comp.get('positionY',0)),comp.get('angle',0),bottom)
   out['drills'].append({'layers':lids,'polygon':[[px*MIL,py*MIL] for px,py in hole_poly]})
  if not net:return
  p=v.get('defaultPad',{});p=p if isinstance(p,dict) else dict(zip(['padType','width','height','cornerRadius'],p))
  w=p.get('width',p.get('diameter',0));h=p.get('height',w);kind=p.get('padType')
  if w<=0 or h<=0:raise ImportErrorDetail('Missing or nonpositive pad dimensions')
  if kind=='ELLIPSE' and w!=h:raise ImportErrorDetail('Noncircular ELLIPSE pad ambiguous; unsupported')
  if kind in ('ELLIPSE','ROUND','OVAL'):
   if w==h:polys=[circle(0,0,w/2,64)]
   elif w>h:polys=stroke_parts([[-(w-h)/2,0],[(w-h)/2,0]],h)
   else:polys=stroke_parts([[0,-(h-w)/2],[0,(h-w)/2]],w)
  elif kind in ('RECT','SQUARE'):
   if p.get('cornerRadius') or p.get('radius'):raise ImportErrorDetail('Rounded rectangular pad unsupported')
   polys=[[[-w/2,-h/2],[w/2,-h/2],[w/2,h/2],[-w/2,h/2]]]
  else:raise ImportErrorDetail('Unsupported pad shape '+str(kind))
  if v.get('specialPad'):raise ImportErrorDetail('Special per-layer pad stack unsupported')
  a=v.get('padAngle',0);cx=comp.get('x',comp.get('positionX',0));cy=comp.get('y',comp.get('positionY',0));ca=comp.get('angle',0)
  conv=lambda ps:transform(transform(ps,x,y,a),cx,cy,ca,bottom)
  center=transform([[x,y]],cx,cy,ca,bottom)[0];layer=v.get('layerId',1)
  layer=2 if bottom and layer==1 else 1 if bottom and layer==2 else layer
  layers=lids if layer in (0,12) else [str(layer)];hole=v.get('hole');holes=[]
  if hole:
   hole=hole if isinstance(hole,dict) else dict(zip(['holeType','width','height'],hole))
   if hole.get('holeType') not in ('ROUND','CIRCLE') or hole.get('width')!=hole.get('height'):raise ImportErrorDetail('Noncircular drill unsupported')
   hw=hole.get('width',0);holes=[conv(circle(v.get('padOffsetX',0),v.get('padOffsetY',0),hw/2))]
   if v.get('padOffsetX') or v.get('padOffsetY'):raise ImportErrorDetail('Offset drill barrel unsupported')
   if v.get('plated') and len(layers)>1:
    out['vias'].append({'net':net,'x':center[0]*MIL,'y':center[1]*MIL,'diameter_mm':min(w,h)*MIL,'drill_mm':hw*MIL,'layers':layers,'length_mm':total,'plating_um':25})
    warn('PTH plating assumed 25 um; verify fabrication specification.')
  label=str(attrs.get(compid,{}).get('Designator',compid or 'PAD'))+'.'+num
  for l in layers:
   for pg in polys:add(net,l,conv(pg),holes)
   out['pins'].append({'id':f'{compid or "PAD"}:{pid}:{l}','label':label+(' / L'+l if len(layers)>1 else ''),'net':net,'layer':l,'x':center[0]*MIL,'y':center[1]*MIL,'radius_mm':max(min(w,h)*MIL/2,0.01)})
 for i,v in bytype('PAD'):
  try:pad(i,v)
  except (ValueError,TypeError,KeyError,IndexError) as e:error(f'Unsupported PAD {i}: {e}')
 for cid,c in bytype('COMPONENT'):
  fid=attrs.get(cid,{}).get('Footprint',c.get('attrs',{}).get('Footprint'));fp=footprints.get(fid)
  if not fp:
   did=attrs.get(cid,{}).get('Device',fid);device=next((d for d in docs if d['head'].get('uuid')==did and d['head'].get('docType')=='DEVICE'),None)
   if device:
    meta=next((v for (t,_),(_,v) in device['records'].items() if t=='META' and v),{});fp=footprints.get(meta.get('attributes',{}).get('Footprint'))
  if not fp:error(f'Footprint not found for {cid}: {fid}');continue
  for (t,i),(_,v) in fp['records'].items():
   if not v:continue
   if t in ('FILL','LINE','ARC','CARC','POLY','TEARDROP') and str(v.get('layerId')) in lids:error(f'Unsupported footprint copper {cid}:{i} ({t})')
   if t=='PAD':
    try:pad(i,v,c,cid)
    except (ValueError,TypeError,KeyError,IndexError) as e:error(f'Unsupported footprint PAD {cid}:{i}: {e}')
 for i,v in bytype('VIA'):
  # 未解析跨度的孔也可能穿过其他网络；仅按本孔网络阻断会漏掉物理孔。
  error(f'VIA {i}: physical drill span rules not yet resolved; cannot safely mask all affected layers.')
 for (typ,i),v in rr.items():
  if typ not in ('PAD','VIA','LINE','ARC','CARC','POLY','FILL','TEARDROP','POUR','POURED') and v.get('netName') and str(v.get('layerId')) in lids:error(f'Unrecognised conductive primitive {typ} {i}',v.get('netName'))
 warn('Experimental importer: verify geometry against EDA; curves discretised at <=4 degrees. Saved pours may be stale; repour before export.')
 return out

def project_boards(path):
 """Discover native pcb/ files, optionally one level of project directories."""
 p=Path(path).expanduser()
 if not p.exists():raise ImportErrorDetail('Project path does not exist: '+str(p))
 if p.is_file():
  if p.stat().st_size>100_000_000:raise ImportErrorDetail('Project file larger than 100 MB')
  if p.suffix.lower()=='.epcb2':return [p.resolve()]
  if p.suffix.lower()!='.eprj3':return []
  if zipfile.is_zipfile(p):return []
  try:index=json.loads(p.read_text(encoding='utf-8-sig'))
  except (ValueError,UnicodeError):return []
  if not isinstance(index,dict) or index.get('format')!='folder':return []
  p=p.parent
 root=p.resolve();found=[]
 # Do not recursively sweep backups or arbitrary directories.
 dirs=[root]+[d for d in root.iterdir() if d.is_dir() and not d.is_symlink() and any(d.glob('*.eprj3'))]
 for d in dirs:
  pcb=d/'pcb'
  if not pcb.is_dir():continue
  for f in pcb.iterdir():
   if f.is_file() and f.suffix.lower()=='.epcb2' and not f.is_symlink() and f.resolve().is_relative_to(root):found.append(f)
 return sorted(found,key=lambda x:str(x).casefold())
def project_choices(path):
 p=Path(path).expanduser();root=(p if p.is_dir() else p.parent).resolve()
 return [str(f.relative_to(root)).replace('\\','/') for f in project_boards(path)]
def archive_choices(data):
 if not zipfile.is_zipfile(io.BytesIO(data)):return []
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  names=[n for n in z.namelist() if n.lower().endswith('.epcb2') and not n.endswith('/')]
  if len(names)!=len(set(names)):raise ImportErrorDetail('Archive has duplicate PCB paths')
  return sorted(names)
def load_project(path,board=None):
 p=Path(path).expanduser()
 if not p.exists():raise ImportErrorDetail('Project path does not exist: '+str(p))
 choices=project_choices(p)
 if choices:
  if board is None and len(choices)>1:raise ImportErrorDetail('Multiple PCBs found; choose one: '+', '.join(choices))
  selected=board if board is not None else choices[0]
  if selected not in choices:raise ImportErrorDetail('PCB selection is not in this project')
  root=p if p.is_dir() else p.parent;p=root/selected
 elif p.is_dir():raise ImportErrorDetail('No pcb/*.epcb2 found in this directory or its immediate project subdirectories')
 if p.stat().st_size>100_000_000:raise ImportErrorDetail('Project file larger than 100 MB')
 return load_project_bytes(p.read_bytes(),p.name,board if not choices else None)
def load_project_bytes(data,filename='board.epcb2',board=None):
 if zipfile.is_zipfile(io.BytesIO(data)):
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   names=archive_choices(data)
   if not names:raise ImportErrorDetail('Archive contains no .epcb2 files')
   if board is None and len(names)!=1:raise ImportErrorDetail(f'Archive has {len(names)} PCB files; choose one')
   selected=board if board is not None else names[0]
   if selected not in names:raise ImportErrorDetail('PCB selection is not in this archive')
   if z.getinfo(selected).file_size>100_000_000:raise ImportErrorDetail('PCB larger than 100 MB')
   return convert(z.read(selected).decode('utf-8-sig'),selected)
 if filename.lower().endswith('.eprj3'):
  try:index=json.loads(data.decode('utf-8-sig'))
  except (ValueError,UnicodeError):index=None
  if isinstance(index,dict) and index.get('format')=='folder':
   raise ImportErrorDetail('This file is a folder-format project index, not the PCB geometry. Upload its complete project ZIP or pcb/<name>.epcb2.')
  raise ImportErrorDetail('Unrecognised standalone .eprj3 contents. This importer supports ZIP containers with one .epcb2 and folder-format indexes with companion files; do not assume this file is incomplete.')
 if filename.lower().endswith('.json'):return json.loads(data.decode('utf-8-sig'))
 return convert(data.decode('utf-8-sig'),filename)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('-o','--output',required=True);a=p.parse_args();d=load_project(a.input);Path(a.output).write_text(json.dumps(d,ensure_ascii=False,indent=2));print(len(d['pins']),'pins;',len(d['copper']),'polygons;',len(d['validation_errors']),'blocking errors')
