import datetime,hashlib,json,shutil
from pathlib import Path
root=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe');stage=Path(__file__).parent;dest=stage/'final-delivery'
run=root/'evidence/runs/20261101-G03-relay-r2';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
changes=json.loads((dest/'changes.json').read_text(encoding='utf-8'))
for item in changes:
    p=root/item['path'];expected=item['before_sha256']
    assert (sha(p) if p.exists() else None)==expected,'Concurrent modification: '+item['path']
    assert sha(dest/item['path'])==item['after_sha256']
out=run/'final-delivery';out.mkdir(exist_ok=False)
for item in changes:
    rel=item['path'];p=root/rel
    if p.exists():
        old=out/'before'/rel;old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,old)
    p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest/rel,p)
    assert sha(p)==item['after_sha256']
shutil.copy2(dest/'changes.json',out/'changes.json')
for n in ['publish-final.py','finalize-staging.py']:
    shutil.copy2(stage/n,out/n)
for n in ['html-build.stdout','html-build.stderr']:
    shutil.copy2(dest/n,out/n)
artifact=json.loads((run/'artifact-manifest.json').read_text(encoding='utf-8'))
for item in artifact['firmware'].values():assert sha(root/item['path'])==item['sha256']
for name in ['board-rehearsal-01','live-01']:
    result=json.loads((run/name/'result.json').read_text(encoding='utf-8'))
    for filename,digest in result['sha256'].items():assert sha(run/name/filename)==digest
inventory={str(p.relative_to(run)).replace('\\','/'):sha(p) for p in run.rglob('*') if p.is_file() and 'final-delivery/before/' not in str(p.relative_to(run)).replace('\\','/')}
(out/'evidence-inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
result=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),published_files=len(changes),all_changed_file_hashes_match=True,all_recorded_raw_hashes_match=True,firmware_hashes_match=True,actual_trigger_count=1,final_output_bits=0,formal_G03_verdict=None)
(out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
