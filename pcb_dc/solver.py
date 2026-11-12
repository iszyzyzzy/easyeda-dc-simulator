"""DC finite-volume sheet resistor solver. Coordinates in mm, copper in um."""
import math
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
from scipy.sparse.csgraph import connected_components
RHO=1.724e-8

def number(v,name):
 v=float(v)
 if not math.isfinite(v):raise ValueError(name+' must be finite')
 return v

def inside(x,y,poly):
 if len(poly)<3:raise ValueError('Polygon needs at least 3 vertices')
 hit=np.zeros(x.shape,bool)
 for a,b in zip(poly,poly[1:]+poly[:1]):
  if a[1]==b[1]:continue
  hit^=((a[1]>y)!=(b[1]>y))&(x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])
 return hit

def solve(project,config):
 if project.get('validation_errors'):raise ValueError('Import incomplete: '+'; '.join(project['validation_errors']))
 if project.get('units','mm')!='mm':raise ValueError('Geometry must use mm')
 net=config['net']
 if project.get('validation_errors_by_net',{}).get(net):raise ValueError('Import incomplete for '+net+': '+'; '.join(project['validation_errors_by_net'][net]))
 h=number(config.get('grid_mm',.5),'grid_mm')
 if h<=0 or h>10:raise ValueError('Grid must be >0 and <=10 mm')
 copper=[c for c in project['copper'] if c['net']==net]
 if not copper:raise ValueError('No copper for selected net')
 layers={str(l['id']):l for l in project['layers']};lids=list(dict.fromkeys(str(c['layer']) for c in copper))
 pts=np.array([p for c in copper for p in c['polygon']],float)
 if not np.isfinite(pts).all():raise ValueError('Nonfinite geometry')
 lo,hi=pts.min(0),pts.max(0);nx,ny=np.ceil((hi-lo)/h).astype(int)
 if min(nx,ny)<1 or nx*ny*len(lids)>160000:raise ValueError('Mesh too large or empty; increase grid spacing (160000 candidate-cell limit)')
 xx,yy=np.meshgrid(lo[0]+(np.arange(nx)+.5)*h,lo[1]+(np.arange(ny)+.5)*h)
 maps={};total=0
 for lid in lids:
  mask=np.zeros(xx.shape,bool)
  for c in copper:
   if str(c['layer'])!=lid:continue
   hit=inside(xx,yy,c['polygon'])
   for hole in c.get('holes',[]):hit&=~inside(xx,yy,hole)
   mask|=hit
  m=np.full(xx.shape,-1,int);n=int(mask.sum());m[mask]=np.arange(total,total+n);total+=n;maps[lid]=m
 if not total:raise ValueError('Mesh contains no copper')
 rho=RHO*(1+.00393*(number(config.get('copper_temperature_c',20),'temperature')-20))
 if rho<=0:raise ValueError('Invalid copper temperature')
 aa=[];bb=[];gg=[];kind=[]
 for lid,m in maps.items():
  t=number(layers[lid].get('thickness_um',35),'thickness_um')*1e-6
  if t<=0:raise ValueError('Copper thickness must be positive')
  for a,b in [(m[:,:-1],m[:,1:]),(m[:-1,:],m[1:,:])]:
   mask=(a>=0)&(b>=0);a=a[mask];b=b[mask];aa.extend(a);bb.extend(b);gg.extend([t/rho]*len(a));kind.extend(['sheet']*len(a))
 warnings=list(project.get('warnings',[]))
 def terminal(lid,x,y,r):
  if lid not in maps:raise ValueError('No copper on terminal layer '+lid)
  m=maps[lid];d=(xx-x)**2+(yy-y)**2;hit=(m>=0)&(d<=r*r)
  if hit.any():return m[hit]
  d=np.where(m>=0,d,np.inf);iy,ix=np.unravel_index(np.argmin(d),d.shape)
  if d[iy,ix]>max(r,h*.8)**2:raise ValueError(f'Terminal/via at {x:g},{y:g} has no resolved copper; reduce grid spacing')
  warnings.append(f'Terminal/via at {x:g},{y:g} snapped to nearest cell.');return np.array([m[iy,ix]])
 if any(v.get('net')==net for v in project.get('vias',[])):
  warnings.append('Via barrel attaches to one resolved copper cell per layer; local via current crowding/loss map is mesh-dependent. Layer spacing is assumed equal when dividing barrel length.')
 for via in project.get('vias',[]):
  if via['net']!=net:continue
  vl=[str(l) for l in via['layers'] if str(l) in lids]
  if len(vl)<2:continue
  drill=number(via['drill_mm'],'drill')*.001;plate=number(via.get('plating_um',25),'plating')*1e-6;length=number(via.get('length_mm',1.6),'via length')*.001
  if min(drill,plate,length)<=0:raise ValueError('Via dimensions must be positive')
  g=math.pi*((drill/2+plate)**2-(drill/2)**2)/(rho*length/(len(vl)-1))
  ids=[terminal(l,float(via['x']),float(via['y']),float(via.get('diameter_mm',.6))/2)[0] for l in vl]
  for a,b in zip(ids,ids[1:]):aa.append(a);bb.append(b);gg.append(g);kind.append('via')
 a,b,g=np.array(aa,int),np.array(bb,int),np.array(gg,float)
 matrix=coo_matrix((np.r_[g,g,-g,-g],(np.r_[a,b,a,b],np.r_[a,b,b,a])),shape=(total,total)).tocsr()
 adj=coo_matrix((np.ones(len(a)*2),(np.r_[a,b],np.r_[b,a])),shape=(total,total)).tocsr();_,labels=connected_components(adj,directed=False)
 pins={p['id']:p for p in project['pins']}
 def pin(pid):
  p=pins[pid]
  if p['net']!=net:raise ValueError('Pin belongs to a different net')
  return terminal(str(p['layer']),float(p['x']),float(p['y']),float(p.get('radius_mm',h/2)))
 source=config['source'];sid=pin(source['pin']);voltage=number(source['voltage_v'],'source voltage');injection=np.zeros(total);loads=[]
 for load in config.get('loads',[]):
  ids=pin(load['pin']);amps=number(load['current_a'],'load current')
  if amps<0:raise ValueError('Current must be nonnegative')
  if np.intersect1d(sid,ids).size:raise ValueError('Source and load overlap in mesh; use finer grid or different terminals')
  injection[ids]-=amps/len(ids);loads.append((load,ids))
 if not loads:raise ValueError('Add at least one current load')
 active=np.isin(labels,np.unique(labels[sid]))
 for load,ids in loads:
  if not active[ids].all():raise ValueError('Disconnected load '+load['pin']+'; check pours, vias and grid')
 if (~active).any():warnings.append(f'{int((~active).sum())} floating copper cells excluded.')
 known=np.zeros(total,bool);known[sid]=True;free=np.flatnonzero(active&~known);v=np.full(total,np.nan);v[sid]=voltage
 if len(free):v[free]=spsolve(matrix[free][:,free],injection[free]-matrix[free][:,sid]@v[sid])
 if not np.isfinite(v[active]).all():raise ValueError('Singular electrical solution')
 valid=active[a]&active[b];ep=np.zeros(len(a));ep[valid]=g[valid]*(v[a[valid]]-v[b[valid]])**2
 power=np.zeros(total);np.add.at(power,a,ep/2);np.add.at(power,b,ep/2)
 total_power=float(ep.sum());via_power=float(ep[np.array(kind)=='via'].sum());reaction=matrix@np.nan_to_num(v)-injection;source_current=float(reaction[sid].sum())
 expected=sum(float(l['current_a']) for l,_ in loads);current_error=abs(source_current-expected);source_power=voltage*source_current
 load_power=sum(float(l['current_a'])*float(v[ids].mean()) for l,ids in loads);energy_error=abs(source_power-load_power-total_power);residual=float(np.max(np.abs(reaction[free]))) if len(free) else 0
 if max(current_error,residual)>1e-6*max(expected,1):raise ValueError('Current balance failed')
 if energy_error>1e-6*max(abs(source_power),total_power,1):raise ValueError('Power balance failed')
 out_layers=[]
 for lid,m in maps.items():
  mask=m>=0;values=np.full(m.shape,np.nan);p=np.full(m.shape,np.nan);values[mask]=v[m[mask]];p[mask]=power[m[mask]]/(h*h)
  clean=lambda z:[[None if not math.isfinite(float(q)) else round(float(q),10) for q in row] for row in z]
  out_layers.append({'id':lid,'name':layers[lid].get('name',lid),'voltage_v':clean(values),'loss_w_mm2':clean(p)})
 outputs=[{'pin':l['pin'],'current_a':float(l['current_a']),'voltage_v':float(v[ids].mean()),'drop_mv':float((voltage-v[ids].mean())*1000),'minimum_voltage_v':float(v[ids].min())} for l,ids in loads]
 theta=config.get('thermal_resistance_k_w');rise=None
 if theta is not None:
  theta=number(theta,'thermal resistance')
  if theta<=0:raise ValueError('Thermal resistance must be positive')
  rise=theta*total_power
 warnings+=['Raster model: refine grid to check convergence; thin necks, gaps and thermal spokes may disappear.', 'Loads distributed over pad cells; no ideal equipotential-pad constraint or connector/contact resistance. Only this net, not the return path.', 'Loss density includes half of each via loss on adjacent cells. Temperature is only total P times user-supplied thermal resistance, not a spatial thermal simulation.']
 return {'net':net,'origin_mm':lo.tolist(),'grid_mm':h,'nx':int(nx),'ny':int(ny),'cells':total,'source_voltage_v':voltage,'source_current_a':source_current,'current_balance_error_a':current_error,'power_balance_error_w':energy_error,'max_kcl_residual_a':residual,'total_loss_w':total_power,'via_loss_w':via_power,'max_drop_mv':float((voltage-np.nanmin(v))*1000),'estimated_temperature_rise_k':rise,'loads':outputs,'layers':out_layers,'warnings':list(dict.fromkeys(warnings))}
