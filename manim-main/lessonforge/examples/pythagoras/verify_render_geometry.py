from pathlib import Path
import json,numpy as np
from manim import config
from chapters_first_four import proof_board,squares_board,tri
R=Path(__file__).resolve().parent
config.tex_dir=str(R/'output/check_tex');Path(config.tex_dir).mkdir(exist_ok=True)
def area(m):
 p=m.get_vertices()[:,:2];return abs(np.dot(p[:,0],np.roll(p[:,1],-1))-np.dot(p[:,1],np.roll(p[:,0],-1)))/2
outer,triangles,central,label,points=proof_board()
e=np.roll(np.array(points),-1,axis=0)-points
assert np.max(np.ptp(np.linalg.norm(e,axis=1)))<1e-8
assert np.max(np.abs(np.sum(e*np.roll(e,-1,axis=0),axis=1)))<1e-8
assert abs(area(outer)-sum(area(t) for t in triangles)-area(central))<1e-8
areas=[area(t) for t in triangles];assert max(areas)-min(areas)<1e-8
lines,qa,qb,qc,labels=squares_board()
assert abs(area(qa[0])+area(qb[0])-area(qc[0]))<1e-8
for q in [qa,qb,qc]:
 p=q[0].get_vertices();v=np.roll(p,-1,axis=0)-p
 assert np.ptp(np.linalg.norm(v,axis=1))<1e-8
 assert np.max(np.abs(np.sum(v*np.roll(v,-1,axis=0),axis=1)))<1e-8
checks={'actual_rendered_proof_geometry':{'outer_area':area(outer),'triangle_areas':areas,'central_area':area(central),'equal_central_sides':True,'right_central_corners':True,'complete_area_partition':True},'actual_outward_square_areas':[area(q[0]) for q in [qa,qb,qc]],'outward_shapes_are_squares':True}
(R/'output/render_geometry_checks.json').write_text(json.dumps(checks,indent=2))
print('Rendered geometry invariants passed')
