"""Small, budgeted text-generation comparison. Secrets are read without echo.

No generated code is executed by this program. No automatic request retries.
"""
import getpass
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
MODELS = ["anthropic/claude-sonnet-4.6", "google/gemini-2.5-flash", "qwen/qwen3-coder-30b-a3b-instruct"]
CAP = 5.0
SYSTEM = "Produce original, accurate educational material. Follow the requested output format. Do not claim validation or learner results."
BRIEF = """Audience: learners aged 14-16 who know coordinates, arithmetic and simple equations. No prior knowledge of slope. Language: conversational English. Topic: understand y=mx+b through an evolving graph. Facts: m=delta y/delta x for nonzero delta x; b is y at x=0; changing b with m fixed translates the line vertically; changing m with b fixed pivots about (0,b); negative slope falls left-to-right; m=0 is horizontal; vertical lines x=c are outside this finite-m form. Avoid saying a larger signed m always means greater steepness. Distinguish intercept from slope. Explain why rather than only stating rules. Keep one running graph and consistent symbol colors. Use prediction pauses, misconceptions, two worked problems and three independent problems with answers. This is an original candidate lesson, not a claimed curriculum mapping."""
TASKS = {
"plan": BRIEF + """\nDesign a complete 20-minute audio-led lesson. Return valid JSON only, with keys: title, prerequisites, notation, sections (8-12 entries with id, duration_seconds, purpose, new_inference, prior_dependency, visual_start_state, visual_actions, visual_end_state, transition_words), worked_problems (2 with solution), independent_problems (3 with answer), opening_narration (350-450 spoken words), misconception_checks. Section durations must sum to exactly 1200. Maintain continuity; do not repeat an introduction for each section. The opening should sound like a teacher reasoning with students, not reading headings. Do not write the entire narration here.""",
"code": """Generate only executable Python code for Manim Community 0.19.0. Class name SlopeInterceptDemo(Scene). No audio, external files, network, subprocesses, imports except manim, math, numpy. Produce a 60-second continuous animation with two related beats, not two restarted slides. Canvas16:9. Keep all teaching content above y=-2.6, reserve bottom for future captions. On the left use equal-unit Cartesian axes covering x[-3,3],y[-3,5], with numeric ticks and an x/y label. On the right show equation and short changing explanations, without overlap. Stage A: line y=x+1, identify (0,1), vary b from1 to2 keeping m=1 and show that delta y/delta x stays1. Stage B: retain same axes, set b=1, vary m from1 to-1 with pivot (0,1); show signed slope and correct rise/run triangle for the final line. Clip plotted lines to visible axis bounds. Use deterministic geometry, correct displayed numbers, stable object identity, correct cleanup of updaters, no use of renderer.time loops. Include intentional thinking pauses, progressive reveals, smooth transitions. Exactly60seconds of play/wait timeline. Use Text for words and MathTex for equations; handle layout widths explicitly. Do not shrink text below22pt. At the end preserve the graph and correct labels. No code fences or commentary.""",
}

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(Path('/tmp/education_openrouter_models.json').read_text())
    prices = {x['id']: x for x in catalog['data']}
    snapshot = {'retrieved_at': datetime.now(timezone.utc).isoformat(), 'source':'https://openrouter.ai/api/v1/models', 'models':[prices[m] for m in MODELS]}
    (ROOT/'model_prices.json').write_text(json.dumps(snapshot, indent=2))
    (ROOT/'prompts.json').write_text(json.dumps({'system':SYSTEM,'tasks':TASKS},indent=2))
    key = getpass.getpass('OpenRouter key (hidden, memory only): ')
    followup = '--followup' in sys.argv
    prior = json.loads((ROOT/'usage.json').read_text()) if followup else {}
    total = prior.get('known_cost_usd',0.0)
    records = prior.get('records',[])
    jobs = [(m,t,TASKS[t],6000) for m in MODELS for t in TASKS]
    jobs.append((MODELS[0],'full_script',BRIEF+"""\nWrite the FULL spoken narration for a roughly20-minute lesson, targeting2400-2700 spoken words plus about90seconds of explicitly marked thinking pauses. Write10sections with natural transitions. Include all required examples and independent problems with answers after pauses. Provide short [VISUAL: ...] cues separate from the spoken text, preserving one evolving board. Finish the lesson; no placeholders or summary standing in for narration. Do not claim exact duration until audio is measured. Return Markdown.""",10000))
    if followup:
        jobs = [(m,'plan_followup',TASKS['plan'],12000) for m in MODELS]
        jobs += [(m,'code_followup',TASKS['code'],6000) for m in MODELS[1:]]
    for model,task,prompt,max_tokens in jobs:
        # Price ceiling applies to each provider; conservative input bound uses UTF-8 bytes.
        listed = prices[model]['pricing']
        input_rate = float(listed['prompt'])*1_000_000*1.10
        output_rate = float(listed['completion'])*1_000_000*1.10
        reserve = ((len(prompt.encode())+len(SYSTEM.encode())+2048)*input_rate+max_tokens*output_rate)/1_000_000 + 0.02
        if total+reserve > CAP:
            print('STOP budget reserve',flush=True);break
        slug=model.replace('/','__')+'__'+task
        payload={'model':model,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':prompt}], 'max_tokens':max_tokens,'temperature':0.3,'provider':{'max_price':{'prompt':input_rate,'completion':output_rate}},'usage':{'include':True}}
        if model.startswith('google/'):
            payload['reasoning']={'enabled':False}
        print('START',slug,'reserved_usd',round(reserve,4),flush=True)
        req=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        t0=time.monotonic()
        try:
            with urllib.request.urlopen(req,timeout=300) as response: result=json.load(response)
        except urllib.error.HTTPError as e:
            # Never log request headers, credentials or arbitrary server error bodies.
            records.append({'model':model,'task':task,'status':'http_error','http_status':e.code,'reserved_usd':reserve})
            (ROOT/'usage.json').write_text(json.dumps({'cap_usd':CAP,'known_cost_usd':total,'records':records},indent=2))
            print('STOP HTTP',e.code,flush=True);break
        except Exception as e:
            records.append({'model':model,'task':task,'status':'unknown_request_outcome','error_type':type(e).__name__,'reserved_usd':reserve})
            (ROOT/'usage.json').write_text(json.dumps({'cap_usd':CAP,'known_cost_usd':total,'records':records},indent=2))
            print('STOP unknown request outcome',type(e).__name__,flush=True);break
        (ROOT/(slug+'.json')).write_text(json.dumps(result,indent=2))
        message=result.get('choices',[{}])[0].get('message',{}).get('content','') or ''
        (ROOT/(slug+'.txt')).write_text(message)
        usage=result.get('usage',{})
        cost=usage.get('cost')
        choice=result.get('choices',[{}])[0]
        status='provider_error' if result.get('error') or choice.get('error') else ('empty_content' if not message.strip() else ('truncated' if choice.get('finish_reason')=='length' else 'returned'))
        rec={'model':model,'task':task,'status':status,'id':result.get('id'),'elapsed_seconds':round(time.monotonic()-t0,2),'usage':usage,'finish_reason':choice.get('finish_reason'),'artifact':slug+'.txt','reserved_usd':reserve}
        records.append(rec)
        if cost is None:
            (ROOT/'usage.json').write_text(json.dumps({'cap_usd':CAP,'known_cost_usd':total,'records':records,'stopped':'missing_cost'},indent=2))
            print('STOP missing authoritative cost',flush=True);break
        total+=float(cost)
        (ROOT/'usage.json').write_text(json.dumps({'cap_usd':CAP,'known_cost_usd':total,'records':records},indent=2))
        print('DONE',slug,'cost_usd',cost,'total_usd',round(total,6),flush=True)
    key=None
    print('FINISHED known_cost_usd',round(total,6),flush=True)

if __name__=='__main__':main()
