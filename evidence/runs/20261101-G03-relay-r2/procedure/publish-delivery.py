"""Publish reviewed staged files only, after checking every original hash."""
from pathlib import Path
import argparse,hashlib,json,shutil,difflib,subprocess,sys
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
root=Path(__file__).parent.resolve();dest=Path('D:/ADMIN/Desktop/WEIJI/zonghe').resolve()
out=root/'evidence/runs/20261101-G03-relay-r2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((root/'baseline-manifest.json').read_text())
extensions={'.c','.h','.py','.uvprojx','.md','.json','.html'}
bases=['BMS_EXv1.1/BMS_EX/BSP','BMS_EXv1.1/BMS_EX/Appli','scripts','tests','instructions']
files={p for b in bases for p in (root/b).rglob('*') if p.is_file() and p.suffix in extensions and '__pycache__' not in str(p)}
files.add(root/'BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/BMS_EX_Appli.uvprojx')
if not a.apply:
    changes=[];diff=[]
    for src in sorted(files):
        rel=str(src.relative_to(root));old=baseline.get(rel)
        if old==sha(src):continue
        target=(dest/rel).resolve();assert dest in target.parents
        if old is not None:assert target.is_file() and sha(target)==old,('Original changed',rel)
        else:assert not target.exists(),('New target exists',rel)
        changes.append(dict(path=rel,before_sha256=old,after_sha256=sha(src)))
        before=out/'before'/rel;after=out/'source-after'/rel
        after.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,after)
        if old:
            before.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,before)
        if src.suffix!='.html':
            diff.extend(difflib.unified_diff(target.read_text(encoding='utf-8-sig').splitlines(True) if old else [],src.read_text(encoding='utf-8-sig').splitlines(True),fromfile='before/'+rel,tofile='after/'+rel))
    (out/'changes.diff').write_text(''.join(diff),encoding='utf-8')
    (out/'delivery-manifest.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(root/'publish-delivery.py',out/'procedure/publish-delivery.py')
    print('Prepared',len(changes),'files; diff and before/after snapshots recorded.');raise SystemExit(0)
changes=json.loads((out/'delivery-manifest.json').read_text(encoding='utf-8'))
target_run=dest/'evidence/runs'/out.name
assert not target_run.exists(),'Refuse to overwrite existing evidence run'
# Check all originals and reviewed staged hashes BEFORE any write.
for c in changes:
    q=(dest/c['path']).resolve();s=(root/c['path']).resolve()
    assert dest in q.parents and root in s.parents
    assert sha(s)==c['after_sha256'],('Staging changed',c['path'])
    assert (q.is_file() and sha(q)==c['before_sha256']) if c['before_sha256'] else not q.exists(),('Destination changed',c['path'])
shutil.copytree(out,target_run)
for c in changes:
    q=dest/c['path'];q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/c['path'],q)
assert all(sha(dest/c['path'])==c['after_sha256'] for c in changes)
(target_run/'delivery-verification.json').write_text(json.dumps(dict(files=len(changes),all_hashes_match=True,source_root=str(dest)),indent=2))
print('Published and verified',len(changes),'files to',dest)

