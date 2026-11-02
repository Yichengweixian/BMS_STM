from pathlib import Path
import subprocess,json,sys
root=Path('D:/ADMIN/Desktop/WEIJI/zonghe');out=root/'evidence/runs/20261031-G03-real-adc-r4'
fw=json.loads((out/'flash-result-02.json').read_text());assert fw['verified']
commands=[('g02-board',[sys.executable,'scripts/g02/host_diagnostics.py','--port','COM9','--out',str(out/'g02-board')]),
('g03-synthetic-board',[sys.executable,'scripts/g03/disabled_diagnostics.py','--port','COM9','--out',str(out/'g03-synthetic-board')]),
('g01-capture',[sys.executable,'scripts/g01/g01_capture.py','--port','COM9','--out',str(out/'g01-capture'),'--seconds','30','--firmware-sha256',fw['sha256']]),
('g01-analyze',[sys.executable,'scripts/g01/analyze_capture.py',str(out/'g01-capture'),'--out',str(out/'g01-analysis.json')])]
results=[]
for name,cmd in commands:
    assert not (out/'raw'/(name+'.stdout')).exists()
    r=subprocess.run(cmd,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=75)
    (out/'raw'/(name+'.stdout')).write_bytes(r.stdout);(out/'raw'/(name+'.stderr')).write_bytes(r.stderr)
    results.append(dict(name=name,command=cmd,exit_code=r.returncode));(out/'regressions.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results[-1]),flush=True)
    if r.returncode:print(json.dumps(r.stderr.decode(errors='replace')),flush=True)
