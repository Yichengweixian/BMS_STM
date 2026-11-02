from pathlib import Path
import hashlib,json,re,subprocess,sys
from urllib.parse import unquote

ROOT=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
STAGE=Path(__file__).parent
RUN=ROOT/'evidence/runs/20261101-G03-current-path-r1'
DOC=STAGE/'documents'
OUT=RUN/'documentation-delivery'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
change=json.loads((DOC/'change-manifest.json').read_text())
for name,entry in change.items():
    assert sha(ROOT/name)==entry['before_sha256'], 'Concurrent edit: '+name
    assert sha(DOC/name)==entry['after_sha256']
assert not (ROOT/'scripts/g03/analyze_current_path.py').exists()
assert not (RUN/'work-card.md').exists()
OUT.mkdir(exist_ok=False)
for name in list(change)+['instructions/BMS实施与验收指南.html']:
    dst=OUT/'before'/name;dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_bytes((ROOT/name).read_bytes())
for name in change:
    (ROOT/name).write_bytes((DOC/name).read_bytes())
(RUN/'work-card.md').write_bytes((DOC/'work-card.md').read_bytes())
(ROOT/'scripts/g03/analyze_current_path.py').write_bytes((STAGE/'analyze_current_path.py').read_bytes())
for name in ('check_probe.py','analyze_current_path.py','plot_current_path.py','prepare_delivery.py','deliver_current_path.py'):
    (RUN/'procedure'/name).write_bytes((STAGE/name).read_bytes())
checks={}
for label,cmd in [('register-mask-check',[sys.executable,str(STAGE/'check_probe.py')]),
                  ('render-html',[r'D:\Program Files\nodejs\node.exe',str(ROOT/'instructions/validation/render_html.cjs')])]:
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=50)
    (OUT/(label+'.stdout')).write_bytes(r.stdout);(OUT/(label+'.stderr')).write_bytes(r.stderr)
    checks[label]=dict(command=cmd,exit_code=r.returncode)
    assert r.returncode==0, r.stderr.decode(errors='replace')
for file in (RUN/'work-card.md',ROOT/'instructions/STATUS.md'):
    for target in re.findall(r'\]\(([^)]+)\)',file.read_text(encoding='utf-8')):
        if target.startswith(('http:','https:','#')):continue
        assert (file.parent/unquote(target.split('#')[0])).exists(),target
checks['new_document_links']='pass'
assert '20261101-G03-current-path-r1' in (ROOT/'instructions/BMS实施与验收指南.html').read_text(encoding='utf-8')
identity=json.loads((ROOT/'evidence/runs/20261101-G03-relay-r2/production-source-manifest.json').read_text())
for entry in identity['files']:assert sha(ROOT/entry['path'])==entry['sha256']
checks['production_sources_unchanged']=len(identity['files'])
for name,entry in identity['firmware'].items():assert sha(ROOT/entry['path'])==entry['sha256']
checks['images_unchanged']=identity['firmware']
raw=json.loads((RUN/'result.json').read_text())
for name,expected in raw['sha256'].items():assert sha(RUN/name)==expected,name
checks['original_capture_artifacts_unchanged']=len(raw['sha256'])
hp=json.loads((ROOT/'instructions/specs/hardware-profile.json').read_text(encoding='utf-8'))
assert hp['mcu_and_afe_current_same_node'] is None
assert hp['g03_pwm_preparation']['power_ready'] is False
checks['unknown_connection_and_power_gate_preserved']=True
(OUT/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'change-manifest.json').write_text(json.dumps(change,indent=2))
(OUT/'artifact-hashes.json').write_text(json.dumps({str(x.relative_to(RUN)):sha(x) for x in RUN.rglob('*') if x.is_file()},indent=2))
print(json.dumps(checks,ensure_ascii=False,indent=2))
