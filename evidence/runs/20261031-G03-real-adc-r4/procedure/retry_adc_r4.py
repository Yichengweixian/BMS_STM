from pathlib import Path
import subprocess,json,datetime
out=Path('D:/ADMIN/Desktop/WEIJI/zonghe/evidence/runs/20261031-G03-real-adc-r4')
assert not (out/'flash-result-02.json').exists()
old=json.loads((out/'flash-result-01.json').read_text());cmd=old['command']
r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
(out/'raw/flash-02.stdout').write_bytes(r.stdout);(out/'raw/flash-02.stderr').write_bytes(r.stderr)
verified=r.returncode==0 and b'Download verified successfully' in r.stdout
old.update(verified=verified,exit_code=r.returncode,end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(out/'flash-result-02.json').write_text(json.dumps(old,indent=2));print(json.dumps(old))
if not verified:print(json.dumps(r.stdout.decode(errors='replace')));raise SystemExit(1)
conn=cmd[:cmd.index('mode=UR')]+['mode=HOTPLUG']
r=subprocess.run(conn+['-rst'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
(out/'raw/reset-02.stdout').write_bytes(r.stdout);(out/'raw/reset-02.stderr').write_bytes(r.stderr)
print(json.dumps({'reset_exit':r.returncode,'output':r.stdout.decode(errors='replace')}))

