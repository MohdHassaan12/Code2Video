"""Independent mathematical checks for the area proof and problem answers."""
import json, math
from pathlib import Path
import sympy as s
R=Path(__file__).resolve().parent
a,b,c=s.symbols('a b c',positive=True)
assert s.expand((a+b)**2-4*a*b/2)==a*a+b*b
def area(points):
    return abs(sum(x*v-y*u for (x,y),(u,v) in zip(points,points[1:]+points[:1])))/2
trials=[]
for aa,bb in [(3,4),(1,1),(.7,2.3),(8,15),(12,5)]:
    # Cyclic points on the four sides of a square of side a+b.
    L=aa+bb; p=[(aa,0),(L,aa),(bb,L),(0,bb)]
    edges=[(u-x,v-y) for (x,y),(u,v) in zip(p,p[1:]+p[:1])]
    squares=[x*x+y*y for x,y in edges]
    dots=[x*u+y*v for (x,y),(u,v) in zip(edges,edges[1:]+edges[:1])]
    assert all(abs(q-aa*aa-bb*bb)<1e-8 for q in squares)
    assert all(abs(q)<1e-8 for q in dots)
    assert abs(area(p)+4*aa*bb/2-L*L)<1e-8
    trials.append({'a':aa,'b':bb,'central_area':area(p),'all_corners_right':True,'area_partition_valid':True})
answers={'opening_diagonal':math.hypot(4,3),'worked_rectangle':math.hypot(6,8),'worked_ladder':math.sqrt(13**2-5**2),'practice_1':math.hypot(5,12),'practice_2':math.sqrt(10**2-6**2),'practice_3_exact':'sqrt(2)','coordinate_distance':math.hypot(5-1,4-1)}
assert [answers[k] for k in ['opening_diagonal','worked_rectangle','worked_ladder','practice_1','practice_2','coordinate_distance']]==[5,10,12,13,8,5]
(R/'output/math_checks.json').write_text(json.dumps({'symbolic_area_identity':True,'independent_geometry_trials':trials,'answers':answers,'limitation':'Checks mathematical construction and answers, not whether every rendered polygon uses these coordinates.'},indent=2))
print('Mathematics checks passed')
