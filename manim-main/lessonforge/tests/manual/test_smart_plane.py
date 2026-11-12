from manim import *
import sys
sys.path.append(".")
from viz_helpers import SmartCoordinatePlane, SceneManager, LayoutStage, set_realistic_background

class TestScene(Scene):
    def construct(self):
        set_realistic_background(self, "white_canvas", dim=0.2)
        
        manager = SceneManager(self)
        with manager.beat("beat 1"):
            plane = SmartCoordinatePlane()
            self.play(Create(plane))
            
            # draw a line and point
            line = plane.smart_line((0,0), (2,3))
            pt = plane.smart_point((2,3), label="(2,3)")
            self.play(Create(line), Create(pt))
            
            # pin the plane
            plane.is_pinned = True
            
        with manager.beat("beat 2"):
            # line and pt should fade out, plane stays
            text = Text("This is beat 2, old point is gone", color=BLACK)
            LayoutStage.position_left(text)
            self.play(Write(text))
            
        self.wait(1)
