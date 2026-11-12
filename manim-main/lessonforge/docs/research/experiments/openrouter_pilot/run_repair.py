"""One diagnostic-guided repair call within the same cumulative US$5 budget."""
import getpass,json,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    ledger=json.loads((ROOT/'usage.json').read_text());total=ledger['known_cost_usd']
    reserve=0.35
    if total+reserve>ledger['cap_usd']:raise RuntimeError('Budget reserve exceeds cap')
    original=(ROOT/'sonnet_original.py').read_text()
    diagnostic="""Observed defects from actual 480p15 render and source inspection:
1. At t27s, equation and graph show b=2 but info1 still states b=1; slope triangle remains anchored to old line. Make all displayed b-state and triangle state correct together.
2. At t48s slope_frac overlaps info_m1n; t56s summary2 overlaps both. summary2 uses minus DOWN, which moves upward. Allocate nonoverlapping right-panel rows; retire obsolete annotations. Keep minimum22pt. Measure text widths, no arbitrary shrinking.
3. Axes use5.6/6=.933 units per x-unit versus6.4/8=.8 per y-unit, violating equal unit scales. Its bottom extends into reserved caption region y<-2.6. Fit axes with equal units and labels into left panel above y=-2.6.
4. Requested60s, source scheduled58s and encoded58.067s. Correct explicit timeline to60s; avoid labeling comments as evidence.
5. Graph labels collide around the intercept and triangle; separate labels and place rise/run explanatory values in a clear dedicated panel when needed.
Preserve pedagogical sequence, same axes throughout, exact clipping to x[-3,3] y[-3,5], correct endpoints and signed slope. Smooth slope change about (0,1). Prefer minimal structural fixes but change the layout enough to satisfy the contract. Keep equation, point label, slope triangle and text synchronized. Final frame must retain correct graph and readable summary. Return complete corrected Python only; class SlopeInterceptDemo. Imports restricted to manim,math,numpy; no I/O,network,subprocess. Do not add claims that the output is validated."""
    prompt=diagnostic+'\n\nOriginal code:\n'+original
    (ROOT/'repair_prompt.txt').write_text(prompt)
    key=getpass.getpass('OpenRouter key (hidden, memory only): ')
    payload={'model':'anthropic/claude-sonnet-4.6','messages':[{'role':'user','content':prompt}],'max_tokens':9000,'temperature':0.2,'provider':{'max_price':{'prompt':3.3,'completion':16.5}},'usage':{'include':True}}
    req=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    start=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=300) as r:d=json.load(r)
    except Exception as e:
        ledger['records'].append({'task':'diagnostic_repair','status':'unknown_request_outcome','error_type':type(e).__name__,'reserved_usd':reserve});(ROOT/'usage.json').write_text(json.dumps(ledger,indent=2));print(type(e).__name__);return
    key=None
    (ROOT/'sonnet_repair_response.json').write_text(json.dumps(d,indent=2))
    text=d.get('choices',[{}])[0].get('message',{}).get('content') or ''
    (ROOT/'sonnet_repair_candidate.txt').write_text(text)
    usage=d.get('usage',{});cost=usage.get('cost')
    ledger['records'].append({'model':payload['model'],'task':'diagnostic_repair','id':d.get('id'),'status':'returned','usage':usage,'finish_reason':d.get('choices',[{}])[0].get('finish_reason'),'elapsed_seconds':round(time.monotonic()-start,2),'artifact':'sonnet_repair_candidate.txt','reserved_usd':reserve})
    if cost is not None:ledger['known_cost_usd']+=cost
    (ROOT/'usage.json').write_text(json.dumps(ledger,indent=2))
    print({'repair_cost_usd':cost,'cumulative_cost_usd':ledger['known_cost_usd']})

if __name__=='__main__':main()
