"""Independent code-generation requests with one pre-reserved shared budget."""
import json,getpass,time,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
R=Path(__file__).resolve().parent
def main():
    tasks=[('chapter5',10000),('chapters678',17000),('chapters910',14000)]
    model='anthropic/claude-sonnet-4.6';ledger=R/'usage.json';data=json.loads(ledger.read_text())
    jobs=[]
    for task,limit in tasks:
        assert not any(x['task']==task for x in data['records'])
        prompt=(R/'prompts'/f'{task}.txt').read_text();reserve=((len(prompt.encode())+2048)*3.3+limit*16.5)/1e6+.02
        jobs.append((task,limit,prompt,reserve))
    prior=data['prior_pilot_usd']+data['new_cost_usd']+sum(x.get('uncertain_reserve',0) for x in data['records'])
    assert prior+sum(j[3] for j in jobs)<=data['cap_usd']
    key=getpass.getpass('OpenRouter key (hidden; memory only): ')
    for task,limit,prompt,reserve in jobs:data['records'].append({'task':task,'status':'in_flight','uncertain_reserve':reserve})
    ledger.write_text(json.dumps(data,indent=2))
    def request(job):
        task,limit,prompt,reserve=job;t=time.monotonic()
        payload={'model':model,'max_tokens':limit,'reasoning':{'enabled':False},'temperature':.3,'messages':[{'role':'user','content':prompt}],'provider':{'max_price':{'prompt':3.3,'completion':16.5}},'usage':{'include':True}}
        req=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=600) as response:result=json.load(response)
            return task,result,round(time.monotonic()-t,2),None
        except Exception as exc:return task,None,round(time.monotonic()-t,2),type(exc).__name__
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(request,j) for j in jobs]):
            task,result,elapsed,error=future.result();record=next(x for x in data['records'] if x['task']==task)
            if error:record.update(status='unknown_outcome',error_type=error)
            else:
                choice=result.get('choices',[{}])[0];content=choice.get('message',{}).get('content','') or '';usage=result.get('usage',{})
                (R/'generated'/f'{task}_response.json').write_text(json.dumps(result,indent=2));(R/'generated'/f'{task}.txt').write_text(content)
                record.update(model=model,usage=usage,finish_reason=choice.get('finish_reason'),characters=len(content),elapsed_seconds=elapsed,status='returned')
                if usage.get('cost') is not None:data['new_cost_usd']+=float(usage['cost']);record.pop('uncertain_reserve',None)
            ledger.write_text(json.dumps(data,indent=2));print('Completed',task,'cost',record.get('usage',{}).get('cost'),'status',record.get('finish_reason',record['status']),flush=True)
    key=None
if __name__=='__main__':main()
