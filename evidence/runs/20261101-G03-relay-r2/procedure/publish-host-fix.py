import hashlib,json,shutil
from pathlib import Path
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
stage=Path(__file__).parent
run=root/'evidence/runs/20261101-G03-relay-r2'
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old={x['path'].replace('\\','/'):x['after_sha256'] for x in json.loads((run/'delivery-manifest.json').read_text(encoding='utf-8'))}
paths=['scripts/g03/relay_capture.py','tests/g03/test_relay_host.py']
for rel in paths:
    assert digest(root/rel)==old[rel],rel
out=run/'host-fix-01'
out.mkdir(exist_ok=False)
records=[]
for rel in paths:
    saved=out/'before'/rel;saved.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/rel,saved)
    shutil.copy2(stage/rel,root/rel)
    assert digest(root/rel)==digest(stage/rel)
    records.append(dict(path=rel,before_sha256=old[rel],after_sha256=digest(root/rel)))
(out/'manifest.json').write_text(json.dumps(dict(reason='Distinguish baseline rejection from a real PG5 command interval; host-only, firmware unchanged',tests='4 host unit tests passed in staging',changes=records),indent=2),encoding='utf-8')
print(json.dumps(records,indent=2))
