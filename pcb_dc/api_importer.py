"""Read-only API snapshot adapter. API geometry is mil, with NO POURED x10 factor."""
import math
try:
 from .importer import MIL,path_points,nonzero_regions,stroke_parts,circle,transform,arc_points
except ImportError:
 from importer import MIL,path_points,nonzero_regions,stroke_parts,circle,transform,arc_points
FORMAT='easyeda-dc-api-snapshot-v1'
def api_path_points(p):
 # API 的 R 第七项是圆角，不是文件格式里的绕向标志。
 if p and p[0]=='R':
  if len(p)!=7 or p[6]:raise ValueError('API rounded rectangle path unsupported')
  _,x,y,w,h,a,_=p
  if w<=0 or h<=0:raise ValueError('Invalid API rectangle dimensions')
  return transform([[0,0],[w,0],[w,-h],[0,-h]],x,y,a)
 if p and p[0]=='CIRCLE' and len(p)!=4:raise ValueError('Unknown API circle path format')
 return path_points(p)

def convert_api_snapshot(s):
 if s.get('format')!=FORMAT or s.get('units')!='mil':raise ValueError('Unsupported API snapshot format/units')
 net=s.get('net');out={'units':'mm','name':'EasyEDA API: '+str(net),'layers':[],'copper':[],'pins':[],'vias':[],'drills':[],'warnings':list(s.get('warnings',[])),'validation_errors':list(s.get('errors',[]))}
 def positive(x):
  x=float(x)
  if not math.isfinite(x) or x<=0:raise ValueError('Expected finite positive dimension')
  return x
 stack=s.get('stack',{})
 try:
  if stack.get('confirmed') is not True:raise ValueError('Physical dimensions must be explicitly confirmed')
  thick=positive(stack['copper_um']);board=positive(stack['board_mm']);plate=positive(stack['plating_um'])
  layers=s['layers'];ids=[str(x['id']) for x in layers]
  if set(ids)!={'1','2'} or len(ids)!=2:raise ValueError('Only an explicitly confirmed two-copper-layer stack is supported')
  out['layers']=[{'id':str(x['id']),'name':x.get('name',str(x['id'])),'thickness_um':thick} for x in layers]
 except (ValueError,KeyError,TypeError) as e:
  out['validation_errors'].append('Stack: '+str(e));return out
 def drill_polygon(poly):
  out['drills'].append({'layers':ids,'polygon':[[x*MIL,y*MIL] for x,y in poly]})
 # 真实钻孔必须在铜并集后扣除，不能被同网走线重新填回。
 if 'physical_holes' not in s:
  out['validation_errors'].append('Snapshot lacks complete physical holes; re-export with the latest plugin')
 for h in s.get('physical_holes',[]):
  try:
   if h['type']=='Via':
    if h['via_type']!=0:raise ValueError('Physical via span not validated')
    d=positive(h['diameter']);center=[h['x'],h['y']]
   elif h['type']=='Pad':
    if h['hole'][0]!='ROUND' or len(h['hole'])!=2:raise ValueError('Non-round physical hole unsupported')
    d=positive(h['hole'][1]);center=transform([[h.get('offset_x',0),h.get('offset_y',0)]],h['x'],h['y'],h.get('rotation',0))[0]
   else:raise ValueError('Unknown physical hole type')
   drill_polygon(circle(*center,d/2))
  except (ValueError,KeyError,TypeError,IndexError) as e:out['validation_errors'].append('Physical hole '+str(h.get('id',''))+': '+str(e))
 def add(layer,p,holes=None):
  if str(layer) not in ids:raise ValueError('Geometry on unknown/noncopper layer '+str(layer))
  if len(p)<3 or not all(math.isfinite(float(a)) for pt in p for a in pt):raise ValueError('Invalid polygon')
  out['copper'].append({'net':net,'layer':str(layer),'polygon':[[x*MIL,y*MIL] for x,y in p],'holes':[[[x*MIL,y*MIL] for x,y in h] for h in holes or []]})
 def stroke(layer,pts,w,closed=False):
  positive(w)
  for poly in stroke_parts(pts,w,closed):add(layer,poly)
 def barrel(r,diameter,drill):
  positive(diameter);positive(drill)
  if drill>=diameter:raise ValueError('Drill must be smaller than copper diameter')
  out['vias'].append({'net':net,'x':r['x']*MIL,'y':r['y']*MIL,'layers':['1','2'],'diameter_mm':diameter*MIL,'drill_mm':drill*MIL,'length_mm':board,'plating_um':plate})
 for r in s.get('primitives',[]):
  try:
   if r.get('net')!=net:raise ValueError('Mixed-net snapshot')
   typ=r['type']
   if typ in ('Line','Arc'):
    start=[r['x1'],r['y1']];end=[r['x2'],r['y2']]
    pts=[start,end] if typ=='Line' else [start]+arc_points(start,end,r['angle'])
    stroke(r['layer'],pts,r['width'])
   elif typ=='Pour':
    if not r.get('fills'):raise ValueError('Missing or empty final copper; repour and verify')
    for f in r['fills']:
     rings=[api_path_points(p) for p in f['path']]
     if f['fill']:
      for outer,holes in nonzero_regions(rings):add(r['layer'],outer,holes)
     if f['width']:
      for ring in rings:stroke(r['layer'],ring,f['width'],bool(f['fill']))
   elif typ in ('Pad','ComponentPad'):
    if r.get('special'):raise ValueError('Per-layer special pad stack unsupported')
    kind,w,h,*extra=r['pad'];positive(w);positive(h)
    if kind=='ELLIPSE':
     if w!=h:raise ValueError('Noncircular ELLIPSE semantics not validated')
     polys=[circle(0,0,w/2,64)]
    elif kind=='RECT':
     if extra and extra[0]:raise ValueError('Rounded rectangular pad unsupported')
     polys=[[[-w/2,-h/2],[w/2,-h/2],[w/2,h/2],[-w/2,h/2]]]
    elif kind=='OVAL':
     polys=stroke_parts([[-(w-h)/2,0],[(w-h)/2,0]],h) if w>=h else stroke_parts([[0,-(h-w)/2],[0,(h-w)/2]],w)
    else:raise ValueError('Unsupported pad shape '+str(kind))
    conv=lambda ps:transform(ps,r['x'],r['y'],r['rotation'])
    lids=ids if r['layer']==12 else [str(r['layer'])];holes=[]
    if r.get('hole'):
     hole=r['hole']
     if hole[0]!='ROUND' or len(hole)!=2:raise ValueError('Non-round drill unsupported')
     if r.get('hole_x') or r.get('hole_y'):raise ValueError('Offset drill unsupported')
     d=positive(hole[1])
     if d>=min(w,h):raise ValueError('Invalid drill/pad dimensions')
     holes=[conv(circle(0,0,d/2))]
     drill_polygon(holes[0])
     if r.get('plated') and len(lids)>1:barrel(r,min(w,h),d)
    for lid in lids:
     for poly in polys:add(lid,conv(poly),holes)
     out['pins'].append({'id':str(r['id'])+':'+lid,'label':r.get('label',str(r['id']))+' / L'+lid,'net':net,'layer':lid,'x':r['x']*MIL,'y':r['y']*MIL,'radius_mm':min(w,h)*MIL/2})
   elif typ=='Via':
    if r['via_type']!=0:raise ValueError('Blind/buried/stitching via span not validated')
    barrel(r,r['diameter'],r['drill'])
    drill_polygon(circle(r['x'],r['y'],r['drill']/2))
    for lid in ids:add(lid,circle(r['x'],r['y'],r['diameter']/2),[circle(r['x'],r['y'],r['drill']/2)])
   else:raise ValueError('Unsupported primitive '+str(typ))
  except (ValueError,KeyError,TypeError,IndexError) as e:out['validation_errors'].append(str(r.get('id','primitive'))+': '+str(e))
 out['warnings'].append('API geometry is mil (no file POURED x10). Two-layer, user-confirmed uniform copper and barrel dimensions; raw API physical stack is retained in snapshot but not guessed. Curve tessellation and grid errors remain.')
 return out
