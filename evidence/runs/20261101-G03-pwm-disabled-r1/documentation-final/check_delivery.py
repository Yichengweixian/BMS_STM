from pathlib import Path
import json,re,hashlib,datetime
R=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe');E=R/'evidence/runs/20261101-G03-pwm-disabled-r1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
production=read(E/'production-source-manifest.json')
assert all(sha(R/v['path'])==v['sha256'] for v in production['files'])
for target,images in production['firmware'].items():
    for image in images.values():assert sha(R/image['path'])==image['sha256']
verified=0
for p in E.glob('board-suite-*/*/result.json'):
    d=read(p)
    for name,value in d.get('sha256',{}).items():assert sha(p.parent/name)==value;verified+=1
for p in (E/'boot-query-01/result.json',E/'reset-failure-query-01/result.json',E/'resource-recovery-01/result.json'):
    for name,value in read(p)['sha256'].items():assert sha(p.parent/name)==value;verified+=1
for name in ('report.md','work-card.md','analysis/comparison.md'):
    p=E/name
    for href in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        if '://' in href or href.startswith('#'):continue
        assert (p.parent/href.split('#')[0]).exists(),(name,href)
assert read(E/'result.json')['disabled_cases_passed']==15
assert read(E/'resource-recovery-01/result.json')['verdict']=='pass'
files=[dict(path=p.relative_to(E).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(E.rglob('*')) if p.is_file() and p.name!='artifact-manifest.json']
delivery=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_files_verified=len(production['files']),
    original_run_hashes_verified=verified,markdown_local_links_verified=True,files=files,
    current_project_files=[dict(path=x,sha256=sha(R/x)) for x in ('instructions/STATUS.md','instructions/RUNLOG.md','instructions/specs/hardware-profile.json','instructions/BMS实施与验收指南.html','scripts/g03/pwm_disabled.py','scripts/g03/bench_pwm_disabled.py','scripts/g03/post_pwm_recovery.py','scripts/g03/run_pwm_checks.py')])
with (E/'artifact-manifest.json').open('x',encoding='utf-8') as f:json.dump(delivery,f,ensure_ascii=False,indent=2)
print(json.dumps(dict(artifact_files=len(files),source_files_verified=len(production['files']),run_hashes_verified=verified,links='pass')))
