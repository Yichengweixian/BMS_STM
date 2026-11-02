import datetime,hashlib,json,shutil,subprocess,sys
from pathlib import Path
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe');stage=Path(__file__).parent;run=root/'evidence/runs/20261101-G03-relay-repeat-r1'
out=run/'software-delivery';out.mkdir(exist_ok=False)
paths=['scripts/g03/compare_relay_runs.py','scripts/g03/pwm_point_plan.py','scripts/g03/plot_relay_comparison.py','tests/g03/test_followup_tools.py']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for rel in paths:assert not (root/rel).exists(),rel
for rel in paths:
    (root/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(stage/rel,root/rel)
for name in ['prepare-repeat.py','ready-repeat.py','inspect-boot.py','recover-boot.py','deliver-tools.py']:
    p=run/'procedure'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(stage/name,p)
cmd=[sys.executable,'-m','unittest','discover','-s',str(root/'tests/g03'),'-p','test_followup_tools.py','-v']
r=subprocess.run(cmd,capture_output=True,cwd=root)
(out/'tests.stdout').write_bytes(r.stdout);(out/'tests.stderr').write_bytes(r.stderr)
(out/'manifest.json').write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files={rel:sha(root/rel) for rel in paths},test_command=cmd,test_exit_code=r.returncode,firmware_changed=False),indent=2),encoding='utf-8')
print(r.stderr.decode(errors='replace'));assert r.returncode==0
cmd=[sys.executable,str(root/'scripts/g03/compare_relay_runs.py'),str(root/'evidence/runs/20261101-G03-relay-r2/live-01'),str(run/'repeat-02'),str(run/'repeat-03'),'--out',str(run/'comparison')]
subprocess.run(cmd,check=True,cwd=root)
subprocess.run([sys.executable,str(root/'scripts/g03/pwm_point_plan.py'),'--root',str(root),'--comparison',str(run/'comparison/comparison.json'),'--out',str(run/'pwm-readiness.json')],check=True,cwd=root)
