"""Inspect actual pilot artifacts; this is not a general visual verifier."""
import ast,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def clean(text):return re.sub(r'^```(?:json|python)?\s*|\s*```$','',text.strip())

def main():
    ledger=json.loads((ROOT/'usage.json').read_text())
    result={'scope':'one topic, matched prompts, no statistical model ranking','known_cost_usd':ledger['known_cost_usd'],'calls':[],'code':[]}
    for rec in ledger['records']:
        path=ROOT/rec.get('artifact','')
        if not path.is_file():continue
        raw=path.read_text();task=rec['task'];name=path.stem
        response=ROOT/(name+'.json')
        if task=='diagnostic_repair':response=ROOT/'sonnet_repair_response.json'
        d=json.loads(response.read_text()) if response.exists() else {}
        ch=d.get('choices',[{}])[0]
        status='provider_error' if d.get('error') or ch.get('error') else ('empty_content' if not raw.strip() else ('truncated' if ch.get('finish_reason')=='length' else 'returned'))
        row={'model':rec['model'],'task':task,'status':status,'provider':d.get('provider'),'cost_usd':rec.get('usage',{}).get('cost'),'finish_reason':ch.get('finish_reason')}
        if task.startswith('plan') and raw.strip():
            try:
                plan=json.loads(clean(raw));sections=plan['sections'];duration=sum(x['duration_seconds'] for x in sections);words=len(plan.get('opening_narration','').split())
                row.update({'valid_json':True,'sections':len(sections),'duration_sum_seconds':duration,'duration_requirement_passed':duration==1200,'opening_words':words,'opening_length_passed':350<=words<=450})
            except (ValueError,KeyError,TypeError) as e:row.update({'valid_json':False,'parse_failure':type(e).__name__})
        result['calls'].append(row)
    for name in ['sonnet_original','gemini_original','qwen_original','sonnet_repaired']:
        p=ROOT/(name+'.py');tree=ast.parse(p.read_text());scheduled=0.0
        # These candidates use sequential, literal-duration self.play/wait calls.
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='self':
                if n.func.attr=='play':scheduled+=next((float(ast.literal_eval(k.value)) for k in n.keywords if k.arg=='run_time'),1.0)
                elif n.func.attr=='wait':scheduled+=float(ast.literal_eval(n.args[0])) if n.args else 1.0
        video=ROOT/'renders'/name/'videos'/name/'480p15/SlopeInterceptDemo.mp4'
        row={'artifact':p.name,'scheduled_seconds':scheduled,'scheduled_duration_passed':scheduled==60,'rendered_video_exists':video.exists()}
        if video.exists():
            probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(video)]));row['encoded_seconds']=float(probe['format']['duration'])
        result['code'].append(row)
    (ROOT/'artifact_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
