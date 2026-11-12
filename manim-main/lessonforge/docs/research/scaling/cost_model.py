"""Reproducible scenario estimates. No network or API key required."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent/'experiments/openrouter_pilot'

def main():
    snapshot=json.loads((PILOT/'model_prices.json').read_text())
    rates={m['id']:{'input':float(m['pricing']['prompt'])*1e6,'output':float(m['pricing']['completion'])*1e6} for m in snapshot['models']}
    strong='anthropic/claude-sonnet-4.6';cheap='qwen/qwen3-coder-30b-a3b-instruct';vision='google/gemini-2.5-flash'
    stages=[
      ('planning',4,8000,2000),('script',10,6000,900),('code',20,6000,1800),
      ('visual_review',20,4000,400),('repair',6,5000,1600),('continuity',2,12000,1200)]
    assignments={
      'premium':{s[0]:strong for s in stages},
      'hybrid':{'planning':strong,'script':strong,'code':cheap,'visual_review':vision,'repair':strong,'continuity':strong},
      'economy_experiment':{s[0]:(vision if s[0]=='visual_review' else cheap) for s in stages}}
    scenarios=[]
    for label,routing in assignments.items():
        items=[]
        for name,n,ti,to in stages:
            model=routing[name];price=rates[model]
            cost=n*(ti*price['input']+to*price['output'])/1e6
            items.append({'stage':name,'calls':n,'input_tokens_each':ti,'output_tokens_each':to,'model':model,'cost_usd':cost})
        llm=sum(x['cost_usd'] for x in items)
        # Explicit hypothetical non-LLM rates; not supplier quotations.
        tts=24000/1e6*15
        render=2*0.5
        review=1.5*20
        storage=0.1
        scenarios.append({'name':label,'stages':items,'llm_usd':llm,'tts_usd':tts,'render_usd':render,'review_usd':review,'storage_usd':storage,'attempt_total_usd':llm+tts+render+review+storage})
    setup={'teacher_examples':5000,'teacher_input_tokens_each':1000,'teacher_output_tokens_each':800,'review_minutes_each':1,'review_usd_hour':20,'engineering_hours':40,'engineering_usd_hour':30,'gpu_count':6,'training_hours':8,'assumed_gpu_usd_hour':3}
    teacher_cost=setup['teacher_examples']*(1000*rates[strong]['input']+800*rates[strong]['output'])/1e6
    setup_total=teacher_cost+5000/60*20+40*30+6*8*3
    result={'status':'illustrative_workload_estimates_not_measured_video_costs','price_source':snapshot['source'],'price_retrieved_at':snapshot['retrieved_at'],'rates_usd_per_million':rates,'lesson_minutes':20,'scenarios':scenarios,'assumptions':{'visual_review_input_tokens':'4000 includes assumed image/video token budget; meter actual provider usage','cache_discount':0,'reasoning':'must be included in completion totals if enabled; no separate allowance here','tts':'24000 characters at assumed $15/M characters','render':'2 CPU worker-hours at assumed $0.50/hour','review':'1.5 human hours at assumed $20/hour','storage':'$0.10 allowance; excludes delivery bandwidth','training':'illustrative only; no GPU throughput/memory profiling performed'},'training_setup':setup,'training_setup_cost_usd':setup_total,'break_even_lessons_by_net_saving':{str(s):setup_total/s for s in [0.25,1,5,10]},'sensitivity':{'extra_five_review_minutes_usd':5/60*20,'repair_20_chunks_prob_0_3_expected_calls':20*0.3,'whole_lesson_all_pass_40_chunks_p98':0.98**40}}
    (ROOT/'cost_scenarios.json').write_text(json.dumps(result,indent=2)+'\n')
    for x in scenarios: print(x['name'],round(x['llm_usd'],4),round(x['attempt_total_usd'],4))
    print('illustrative training setup',round(setup_total,2))

if __name__=='__main__':main()
