from pathlib import Path
import tempfile, shutil, json, subprocess, hashlib
stage=Path(__file__).resolve().parent
candidate=stage/'d74-candidate-r1'
root=Path('D:/ADMIN/Desktop/WEIJI/zonghe')
source=Path(tempfile.mkdtemp(prefix='g03d74c1-'))
manifest=json.loads((root/'evidence/runs/20261102-G03-discharge-sprint-r4/production-source-manifest.json').read_text())
for rel in manifest:
    src=candidate/'workspace'/rel
    if not src.exists():src=root/rel
    dest=source/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
for rel in ('BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/RTE','BMS_EXv1.1/BMS_EX/Secure_nsclib'):
    shutil.copytree(root/rel,source/rel,dirs_exist_ok=True)
project=source/'BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/BMS_EX_Appli.uvprojx'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source_hashes={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
build=candidate/'build';build.mkdir(exist_ok=False)
(build/'source-manifest.json').write_text(json.dumps(source_hashes,indent=2))
(build/'source-location.json').write_text(json.dumps({'path':str(source),'runtime_unchanged':True},indent=2))
target='BMS_PWM_Power_Release';log=build/(target+'.log')
cmd=['D:/K5/UV4/UV4.exe','-r',str(project),'-t',target,'-o',str(log)]
r=subprocess.run(cmd,capture_output=True,timeout=240,cwd=project.parent)
(build/'command.json').write_text(json.dumps({'argv':cmd,'exit_code':r.returncode},indent=2))
text=log.read_text(errors='replace');print(text[-2500:])
assert r.returncode in (0,1) and '0 Error(s)' in text
image=project.parent/target/(target+'.hex');assert image.exists()
firmware=candidate/'firmware';firmware.mkdir()
for ext in ('hex','bin','axf','map'):
    path=project.parent/target/(target+'.'+ext)
    if path.exists():shutil.copy2(path,firmware/path.name)
(build/'image-manifest.json').write_text(json.dumps({p.name:sha(p) for p in firmware.iterdir()},indent=2))
for rel,h in source_hashes.items():
    assert sha(source/rel)==h, 'build changed input '+rel
shutil.copytree(source,candidate/'build-source',ignore=shutil.ignore_patterns('BMS_PWM_Power_Release'))
result=json.loads((candidate/'result.json').read_text());result.update(arm_image_built=True,release_hex_sha256=sha(image),arm_build_exit_code=r.returncode)
(candidate/'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
