"""Measure initial axes in the inspected candidates before any animation."""
import importlib.util,inspect,json
from pathlib import Path
import numpy as np
from manim import Scene,config

ROOT=Path(__file__).resolve().parent
class StopAfterMeasurement(Exception):pass

def main():
    results=[]
    original=Scene.play
    def intercept(self,*args,**kwargs):
        context=inspect.currentframe().f_back.f_locals
        axes=context['axes'];origin=axes.c2p(0,0)
        xunit=float(np.linalg.norm(axes.c2p(1,0)-origin));yunit=float(np.linalg.norm(axes.c2p(0,1)-origin))
        top=float(axes.get_top()[1]);bottom=float(axes.get_bottom()[1])
        results.append({'candidate':current,'x_unit':xunit,'y_unit':yunit,'equal_units':abs(xunit-yunit)<1e-6,'axes_top':top,'axes_bottom':bottom,'axes_caption_clear':bottom>=-2.6,'axes_in_frame':top<=config.frame_height/2 and bottom>=-config.frame_height/2,'scope':'initial axes only; labels and temporal collisions require separate inspection'})
        raise StopAfterMeasurement()
    Scene.play=intercept
    try:
        for current in ['sonnet_original','gemini_original','qwen_original','sonnet_repaired']:
            spec=importlib.util.spec_from_file_location(current,ROOT/(current+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            try:module.SlopeInterceptDemo().construct()
            except StopAfterMeasurement:pass
    finally:Scene.play=original
    (ROOT/'initial_geometry_checks.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
