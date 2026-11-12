"""Review generated source structure before running it; not a security sandbox."""
import ast,json,sys,re
from pathlib import Path
R=Path(__file__).resolve().parent
lesson=json.loads((R/'lesson.json').read_text())
beats={b['id']:b for c in lesson['chapters'] for b in c['beats']}
normalize=lambda x:re.sub(r'[^a-z0-9 ]','',x.lower())
for part in sys.argv[1:]:
    source=(R/'generated'/f'{part}.txt').read_text().strip()
    if source.startswith('```'):source='\n'.join(source.splitlines()[1:-1])
    tree=ast.parse(source)
    issues=[]
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            names=[node.module] if isinstance(node,ast.ImportFrom) else [a.name for a in node.names]
            for name in names:
                if name not in ['lesson_runtime','manim','math','numpy']:issues.append(f'Unexpected import: {name}')
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ['exec','eval','open','compile','__import__']:issues.append(f'Unexpected call: {node.func.id}')
    cues=[];starts=[]
    for cls in [n for n in tree.body if isinstance(n,ast.ClassDef)]:
        current=None
        for n in ast.walk(cls):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.args:
                if n.func.attr=='begin' and isinstance(n.args[0],ast.Constant):
                    current=str(n.args[0].value).zfill(2);starts.append(current)
                if n.func.attr=='cue' and isinstance(n.args[0],ast.Constant):
                    phrase=n.args[0].value
                    # AST traversal can interleave nested scopes: check membership in any narration,
                    # while runtime enforces the active beat precisely.
                    exists=any(normalize(phrase) in normalize(b['narration']) for b in beats.values())
                    cues.append({'phrase':phrase,'found':exists})
                    if not exists:issues.append('Missing spoken cue: '+phrase)
    report={'file':part,'classes':[n.name for n in tree.body if isinstance(n,ast.ClassDef)],'beats':starts,'cue_count':len(cues),'issues':issues}
    (R/'generated'/f'{part}_static_check.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    if not any(x.startswith('Unexpected') for x in issues):
        (R/f'chapters_{part}.py').write_text('# Premium model source; see generated/ and editorial_changes.json for provenance.\n'+source+'\n')
    else:raise SystemExit('Review unexpected operations before execution')
