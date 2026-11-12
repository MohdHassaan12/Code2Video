from manim import *

class SnellsLaw(Scene):
    def construct(self):
        title = Title("Snell's Law & Fermat's Principle").to_edge(UP)
        self.play(Write(title))
        
        # Interface: Air (top) / Water (bottom)
        water = Rectangle(width=14, height=4, color=BLUE, fill_opacity=0.3).to_edge(DOWN, buff=0)
        interface = Line([-7, 0, 0], [7, 0, 0], color=WHITE)
        self.play(FadeIn(water), Create(interface))
        
        # Incident and refracted rays
        p_air = [-4, 3, 0]
        p_interface = [0, 0, 0]
        p_water = [2, -3, 0]
        ray_air = Arrow(p_air, p_interface, buff=0, color=YELLOW)
        ray_water = Arrow(p_interface, p_water, buff=0, color=YELLOW)
        
        self.play(GrowArrow(ray_air), GrowArrow(ray_water))
        self.wait(2)