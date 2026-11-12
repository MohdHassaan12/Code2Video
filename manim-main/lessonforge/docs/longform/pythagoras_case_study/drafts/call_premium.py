"""One budgeted OpenRouter request. Credential stays in process memory."""
import getpass, json, sys, time, urllib.request, urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    task=sys.argv[1]
    prompt=(ROOT/'prompts'/f'{task}.txt').read_text()
    model='anthropic/claude-sonnet-4.6'
    catalog=json.loads(Path('/tmp/education_openrouter_models.json').read_text())
    entry=next(m for m in catalog['data'] if m['id']==model)
    ledger=ROOT/'usage.json'
    data=json.loads(ledger.read_text()) if ledger.exists() else {'cap_usd':5.0,'prior_pilot_usd':0.48565189,'new_cost_usd':0.,'records':[]}
    assert not any(r['task']==task for r in data['records']), 'Use a new task name; no accidental retries'
    max_tokens=int(sys.argv[2]) if len(sys.argv)>2 else 18000
    ir=float(entry['pricing']['prompt'])*1e6*1.1
    outr=float(entry['pricing']['completion'])*1e6*1.1
    reserve=((len(prompt.encode())+2048)*ir+max_tokens*outr)/1e6+.02
    committed=data['prior_pilot_usd']+data['new_cost_usd']+sum(r.get('uncertain_reserve',0) for r in data['records'])
    assert committed+reserve <= data['cap_usd'], 'Budget reserve exceeded'
    key=getpass.getpass('OpenRouter key (hidden; memory only): ')
    payload={'model':model,'max_tokens':max_tokens,'temperature':0.35,'reasoning':{'enabled':False},'messages':[{'role':'user','content':prompt}], 'provider':{'max_price':{'prompt':ir,'completion':outr}},'usage':{'include':True}}
    request=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    print('Request',task,'reserve USD',round(reserve,4),flush=True)
    start=time.monotonic()
    try:
        with urllib.request.urlopen(request,timeout=600) as response: result=json.load(response)
    except Exception as exc:
        data['records'].append({'task':task,'status':'unknown_outcome','exception_type':type(exc).__name__,'uncertain_reserve':reserve})
        ledger.write_text(json.dumps(data,indent=2)); raise SystemExit('Request failed; reserve retained; no retry')
    key=None
    (ROOT/'generated'/f'{task}_response.json').write_text(json.dumps(result,indent=2))
    choice=result.get('choices',[{}])[0]
    content=choice.get('message',{}).get('content','') or ''
    (ROOT/'generated'/f'{task}.txt').write_text(content)
    usage=result.get('usage',{}); cost=usage.get('cost')
    record={'task':task,'model':model,'usage':usage,'finish_reason':choice.get('finish_reason'),'elapsed_seconds':round(time.monotonic()-start,2),'characters':len(content)}
    if cost is None: record['uncertain_reserve']=reserve
    else: data['new_cost_usd']+=float(cost)
    data['records'].append(record);ledger.write_text(json.dumps(data,indent=2))
    (ROOT/'model_price_snapshot.json').write_text(json.dumps(entry,indent=2))
    print('Complete',json.dumps(record),flush=True)
if __name__=='__main__':main()
