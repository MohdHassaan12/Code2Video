"""Reviewed implementation of premium-generated chapters 1–4.
Rebuilt shared geometry and panel transitions after inspecting initial renders.
Raw premium source remains in generated/first_four.txt.
"""
from lessonforge.longform.runtime import *
import numpy as np
import math

def tri(a=4,b=3,center=(-3.2,0,0),scale=.85,labels=('4 m','3 m','?')):
    o=np.array(center)-np.array([a*scale/2,b*scale/2,0]);A=o;B=o+RIGHT*a*scale;C=B+UP*b*scale
    lines=VGroup(Line(A,B,color=TEAL,stroke_width=5),Line(B,C,color=GOLD,stroke_width=5),Line(A,C,color=PINK,stroke_width=5))
    mark=RightAngle(Line(B,A),Line(B,C),length=.2,color=INK)
    lab=VGroup(txt(labels[0],27,TEAL).next_to(lines[0],DOWN,buff=.18),txt(labels[1],27,GOLD).next_to(lines[1],RIGHT,buff=.18),txt(labels[2],27,PINK).move_to((A+C)/2+np.array([-.3,.28,0])))
    return VGroup(lines,mark,lab),A,B,C

def square_grid(origin,u,v,n,color):
    poly=Polygon(origin,origin+u,origin+u+v,origin+v,color=color,fill_opacity=.17,stroke_width=2.5)
    grid=VGroup(*[Line(origin+i*u/n,origin+i*u/n+v,color=color,stroke_opacity=.3,stroke_width=1) for i in range(1,n)],*[Line(origin+i*v/n,origin+i*v/n+u,color=color,stroke_opacity=.3,stroke_width=1) for i in range(1,n)])
    return VGroup(poly,grid)

def squares_board():
    s=.4;A=np.array([-4.45,-.6,0]);B=A+RIGHT*4*s;C=B+UP*3*s
    lines=VGroup(Line(A,B,color=TEAL,stroke_width=4),Line(B,C,color=GOLD,stroke_width=4),Line(A,C,color=PINK,stroke_width=4),RightAngle(Line(B,A),Line(B,C),length=.14))
    qa=square_grid(A,RIGHT*4*s,DOWN*4*s,4,TEAL)
    qb=square_grid(B,UP*3*s,RIGHT*3*s,3,GOLD)
    qc=square_grid(A,C-A,np.array([-3*s,4*s,0]),5,PINK)
    labels=VGroup(eq('16',36,TEAL).move_to(qa[0]),eq('9',36,GOLD).move_to(qb[0]),eq('25',36,PINK).move_to(qc[0]))
    for m in labels:m.add_background_rectangle(color=BG,opacity=.9,buff=.08)
    return lines,qa,qb,qc,labels

def proof_board():
    a,b=4.,3.;s=.57;o=np.array([-5.35,-2.,0]);P=lambda x,y:o+np.array([x*s,y*s,0])
    corners=[P(0,0),P(7,0),P(7,7),P(0,7)]
    center=[P(a,0),P(7,a),P(b,7),P(0,b)]
    triangles=VGroup()
    for i in range(4):
        pts=[corners[i],center[i],center[(i-1)%4]]
        triangles.add(Polygon(*pts,color=INK,stroke_width=1.5,fill_color=TEAL if i%2==0 else GOLD,fill_opacity=.22))
    outer=Polygon(*corners,color=MUTED,stroke_width=2)
    inner=Polygon(*center,color=PINK,stroke_width=4,fill_opacity=.12)
    label=eq('a+b',32).next_to(outer,DOWN,buff=.15)
    return outer,triangles,inner,label,center

class C01(LessonScene):
    def construct(self):
        self.chapter(1);g,A,B,C=tri(center=(-3.3,.2,0));lines,mark,labs=g
        floor=Polygon(A,B,C,np.array([A[0],C[1],0]),color=GRID,fill_opacity=.35)
        robot=Dot(A,radius=.085,color=INK)
        self.begin('01');self.cue('Picture a rectangular warehouse floor',Create(floor),FadeIn(robot))
        self.cue('It could travel four metres east',Create(lines[0]),FadeIn(labs[0]),robot.animate.move_to(B),run_time=1.8)
        self.cue('then three metres north',Create(lines[1]),FadeIn(labs[1]),robot.animate.move_to(C),run_time=1.4)
        self.cue('That route covers seven metres',self.panel_to(eq(r'4+3=7\ \mathrm{m}',46),txt('Along the walls',28,MUTED)))
        self.cue('But the robot can also drive straight',Create(lines[2]),FadeIn(labs[2]),self.panel_to(txt('How long is the shortcut?',28),eq('c=?',54,PINK)))
        self.finish()
        self.begin('02');self.cue('Look at those three line segments',FadeOut(floor),FadeOut(robot))
        self.cue('Where the two legs meet',Create(mark),self.panel_to(txt('A right triangle',32),eq(r'90^\circ',54)))
        self.cue('Keep watching that mark',Indicate(mark,color=GOLD,scale_factor=1.7));self.finish()
        self.begin('03');self.cue('Before calculating, estimate',self.panel_to(txt('Estimate first',30),eq('4<c<7',54,PINK)))
        self.cue('The diagonal is longer than either leg',Indicate(lines[2]),Indicate(lines[0]))
        self.cue('But the straight path is shorter',ShowPassingFlash(lines[0].copy().set_color(INK)),ShowPassingFlash(lines[1].copy().set_color(INK)))
        self.cue('An estimate gives us a way',Circumscribe(self.panel,color=PINK));self.finish()
        self.begin('04');self.cue('Why would anyone think to square',self.panel_to(txt('Why squares?',36),eq(r'4^2+3^2\;?',52)))
        self.cue('Adding four and three gives seven',self.panel_to(eq('4+3=7',46),txt('A route length',28,MUTED)))
        self.cue('Squaring has a geometric meaning',self.panel_to(txt('Length becomes area',30),eq(r'4\times4=4^2',44,TEAL)))
        tile=Square(.7,color=TEAL,fill_opacity=.2).move_to([-3.5,1.3,0])
        self.cue('How could comparing areas',Create(tile),self.panel_to(txt('Area can reveal a length',28),eq(r'\text{length}\;\longrightarrow\;\text{area}',34)))
        self.finish();self.done()

class C02(LessonScene):
    def construct(self):
        self.chapter(2);lines,qa,qb,qc,labs=squares_board()
        self.begin('05');self.cue('Let us build a square',Create(lines))
        self.cue('On the four-metre teal leg',Create(qa),run_time=1.8)
        self.cue('Its area is four times four',FadeIn(labs[0]),self.panel_to(eq(r'4^2=16\ \mathrm{m}^2',44,TEAL)))
        self.cue('On the three-metre gold leg',Create(qb),run_time=1.5)
        self.cue('Its area is three times three',FadeIn(labs[1]),self.panel_to(eq('4^2=16',44,TEAL),eq('3^2=9',44,GOLD),txt('Areas in square metres',25,MUTED)))
        self.cue('Each little unit cell',Indicate(qa[1],color=INK));self.finish()
        self.begin('06');self.cue('Now add those two areas together',self.panel_to(eq('16+9=25',50)))
        self.cue('the square built on the diagonal',Create(qc),run_time=2)
        self.cue('also has an area of exactly twenty-five',FadeIn(labs[2]))
        self.cue('The square root of twenty-five is five',self.panel_to(eq(r'c^2=25\ \mathrm{m}^2',40),eq(r'c=\sqrt{25}=5\ \mathrm{m}',42,PINK)))
        self.cue('Those are different things with different units',Circumscribe(self.panel,color=GOLD));self.finish()
        self.begin('07');self.cue('Five lies between four and seven',self.panel_to(eq('4<5<7',46),txt('A sensible answer',28)))
        self.cue('Now call the teal leg a',Transform(labs[0],eq('a^2',38,TEAL).move_to(qa[0])),Transform(labs[1],eq('b^2',38,GOLD).move_to(qb[0])),Transform(labs[2],eq('c^2',38,PINK).move_to(qc[0])))
        self.cue('The relationship is c squared',self.panel_to(eq('c^2=a^2+b^2',46)))
        self.cue('But checking one example is evidence',self.panel_to(eq('c^2=a^2+b^2',44),txt('An example is not a proof',27,GOLD)));self.finish()
        self.begin('08');self.cue('A proof must work for any positive lengths',self.panel_to(txt('Any positive a and b',30),eq(r'a^2+b^2\stackrel{?}{=}c^2',44)))
        self.cue('The claim is that the square on the hypotenuse',Indicate(qc[0],color=PINK),Indicate(qa[0],color=TEAL),Indicate(qb[0],color=GOLD))
        self.cue('We will build an argument',self.panel_to(txt('What stays true?',34),txt('Explain the area equality',28,MUTED)))
        self.finish();self.done()

class C03(LessonScene):
    def construct(self):
        self.chapter(3);g,A,B,C=tri(labels=('a','b','c'));lines,mark,labs=g
        self.begin('09');self.cue('Find the right-angle mark',Create(lines),Create(mark),FadeIn(labs))
        self.cue('The side opposite that corner',Indicate(lines[2],color=PINK),self.panel_to(txt('Opposite the right angle',28),txt('HYPOTENUSE',34,PINK)))
        self.cue('These names describe relationships',self.panel_to(txt('Position can change',30),txt('The relationship stays',28,MUTED)));self.finish()
        self.begin('10');angle=PI-math.atan2(3,4)
        self.cue('Watch the whole triangle rotate',Rotate(g,angle=angle,about_point=np.array([-3.2,0,0])),run_time=2.5)
        for lab in labs:lab.rotate(-angle)
        self.cue('The right-angle mark has moved to the top',Indicate(mark,color=GOLD,scale_factor=1.5))
        self.cue('Pink is still opposite the right angle',Indicate(lines[2],color=PINK))
        self.cue('The formula remains',self.panel_to(eq('c^2=a^2+b^2',46)));self.finish()
        self.begin('11');self.play(FadeOut(g),run_time=.4)
        pivot=np.array([-3.9,-1.3,0]);end=pivot+RIGHT*2.5
        def endpoint(t):return pivot+1.875*np.array([math.cos(t),math.sin(t),0])
        l1=Line(pivot,end,color=TEAL,stroke_width=5);l2=Line(pivot,endpoint(PI/2),color=GOLD,stroke_width=5);h=Line(end,endpoint(PI/2),color=PINK,stroke_width=5)
        angletext=DecimalNumber(90,num_decimal_places=0,unit=r'^\circ',font_size=27,color=INK).move_to(pivot+np.array([.5,.35,0]))
        sizes=VGroup(txt('4',27,TEAL).next_to(l1,DOWN),txt('3',27,GOLD).next_to(l2,LEFT))
        self.cue('Now keep the three-metre and four-metre legs fixed',Create(l1),Create(l2),Create(h),FadeIn(sizes),FadeIn(angletext))
        moving=VGroup(l2,h,angletext,sizes[1])
        def sweep(start,finish):
            def update(m,alpha):
                theta=start+(finish-start)*alpha;angletext.set_value(np.degrees(theta));p=endpoint(theta);l2.put_start_and_end_on(pivot,p);h.put_start_and_end_on(end,p);sizes[1].next_to(l2,LEFT)
            return UpdateFromAlphaFunc(moving,update)
        self.cue('Open the angle beyond ninety degrees',sweep(PI/2,2*PI/3),self.panel_to(txt('Same legs',30),txt('Longer opposite side',28,PINK)),run_time=2.3)
        self.cue('Close it below ninety',sweep(2*PI/3,PI/3),self.panel_to(txt('Same legs',30),txt('Shorter opposite side',28,PINK)),run_time=2.3)
        self.cue('Three and four give five only when',sweep(PI/3,PI/2),self.panel_to(txt('Right angle required',30),eq('c=5',46,PINK)),run_time=2.3);self.finish()
        self.begin('12');self.cue('Return the corner to ninety degrees',Indicate(angletext,color=GOLD))
        self.cue('Notice that a plus b does not equal c',self.panel_to(eq(r'a+b\ne c',48),eq(r'4+3=7\ne5',42)))
        self.cue('The theorem combines the squares',self.panel_to(eq(r'c=\sqrt{a^2+b^2}',46),txt('Compare areas, then lengths',26,MUTED)))
        self.finish();self.done()

class C04(LessonScene):
    def construct(self):
        self.chapter(4);outer,tris,inner,side,points=proof_board()
        self.begin('13');self.cue('Let us build the proof',Create(outer))
        self.cue('Take a right triangle',Create(tris[0]))
        self.cue('Make four identical copies',LaggedStart(*[Create(t) for t in tris[1:]],lag_ratio=.35),run_time=2)
        self.cue('Around each outer edge',FadeIn(side),self.panel_to(eq(r'\text{side}=a+b',42),txt('Four identical triangles',28)))
        self.cue('The four hypotenuses enclose',Create(inner),run_time=1.5);self.finish()
        self.begin('14');self.cue('Is that central shape really a square',self.panel_to(txt('Looks like a square?',30),txt('We must justify it',28,GOLD)))
        self.cue('Each of its four sides is the hypotenuse',Indicate(inner,color=PINK),self.panel_to(eq(r'c,\ c,\ c,\ c',46,PINK),txt('Four equal sides',28)))
        p=points[0];beta=math.atan2(4,3);alpha=math.atan2(3,4)
        arcs=VGroup(Arc(radius=.55,start_angle=PI-alpha,angle=alpha,arc_center=p,color=TEAL),Arc(radius=.55,start_angle=0,angle=beta,arc_center=p,color=GOLD))
        angles=VGroup(eq(r'\alpha',25,TEAL).move_to(p+np.array([-.72,.18,0])),eq(r'\beta',25,GOLD).move_to(p+np.array([.69,.35,0])))
        self.cue('Focus on one central corner',Create(arcs),FadeIn(angles),run_time=1.6)
        self.cue('Call those acute angles alpha and beta',self.panel_to(txt('Now check the angles',29),eq(r'\alpha+\beta=90^\circ',42)));self.finish()
        self.begin('15');self.cue('The angles inside a triangle total',self.panel_to(eq(r'90^\circ+\alpha+\beta=180^\circ',36)))
        self.cue('so alpha and beta together total ninety degrees',self.panel_to(eq(r'\alpha+\beta=90^\circ',42)))
        theta=Arc(radius=.38,start_angle=beta,angle=PI/2,arc_center=p,color=INK,stroke_width=3)
        th=eq(r'\theta',26).move_to(p+np.array([-.13,.62,0]))
        self.cue('At the central corner',Create(theta),FadeIn(th),self.panel_to(eq(r'\alpha+\theta+\beta=180^\circ',35)))
        self.cue('The central angle is therefore',self.panel_to(eq(r'\theta=180^\circ-90^\circ',37),eq(r'\theta=90^\circ',46,PINK)))
        marks=VGroup(*[RightAngle(Line(points[i],points[(i-1)%4]),Line(points[i],points[(i+1)%4]),length=.17,color=INK) for i in range(4)])
        self.cue('The same reasoning works at all four corners',Create(marks))
        self.cue('Equal sides and right angles',self.panel_to(txt('The centre IS a square',29),eq(r'\text{area}=c^2',48,PINK)));self.finish()
        self.begin('16');self.play(FadeOut(arcs),FadeOut(angles),FadeOut(theta),FadeOut(th),run_time=.5)
        self.cue('Check our three-four-five example',Transform(side,eq('3+4=7',32).move_to(side)),self.panel_to(eq('7^2=49',48)))
        self.cue('Each triangle has area',Indicate(tris[0]),self.panel_to(eq(r'\tfrac12(3)(4)=6',42)))
        self.cue('Four triangles occupy twenty-four',Indicate(tris),self.panel_to(eq(r'4\times6=24',46)))
        self.cue('The space remaining',inner.animate.set_fill(PINK,opacity=.35),self.panel_to(eq('49-24=25',48),eq(r'c=\sqrt{25}=5',44,PINK)))
        self.cue('Now we will repeat this calculation with letters',Circumscribe(self.panel,color=GOLD));self.finish();self.done()
