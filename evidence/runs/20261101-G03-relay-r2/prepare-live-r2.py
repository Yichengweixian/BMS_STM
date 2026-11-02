from pathlib import Path
import shutil,hashlib,json
original=Path('D:/ADMIN/Desktop/WEIJI/zonghe');root=Path(__file__).parent.parent/'g03-live-work'
root.mkdir(exist_ok=False)
baseline={}
for name in ['BMS_EXv1.1','scripts','tests','instructions']:
    shutil.copytree(original/name,root/name,ignore=shutil.ignore_patterns('__pycache__','*.uvguix.*'))
for name in ['AGENTS.md','README.md']:shutil.copy2(original/name,root/name)
for d in ['BMS_EXv1.1','scripts','tests','instructions']:
    for p in (root/d).rglob('*'):
        if p.is_file():baseline[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
(root/'baseline-manifest.json').write_text(json.dumps(baseline,indent=2))
# Preserve all historical parser identities while identifying this new firmware.
for base in ['BMS_EXv1.1/BMS_EX/BSP','scripts','tests']:
    for p in (root/base).rglob('*'):
        if p.suffix not in ('.c','.h','.py'):continue
        s=p.read_text(encoding='utf-8-sig')
        if 'g03-relay-r1' not in s:continue
        if base=='scripts':
            s=s.replace("'g03-adc-r4','g03-relay-r1'","'g03-adc-r4','g03-relay-r1','g03-relay-r2'")
            s=s.replace("firmware!='g03-relay-r1'","firmware not in ('g03-relay-r1','g03-relay-r2')")
        else:s=s.replace('g03-relay-r1','g03-relay-r2')
        p.write_text(s,encoding='utf-8')
profile=root/'BMS_EXv1.1/BMS_EX/BSP/g03_relay_profile.h'
profile.write_text('''#ifndef G03_RELAY_PROFILE_H
#define G03_RELAY_PROFILE_H
/* Frozen exploratory raw-code envelope, derived from board-rehearsal-01.
 * NOT manufacturer cell limits or calibrated absolute-current protection.
 * 38865..38872 cell codes observed; stop on a 500-code (~50 mV nominal)
 * departure from that measured envelope. GPIO1 baseline 8994..9006,
 * with 36-code (3x observed peak-to-peak) drift margin fixed before live. */
#ifndef G3R_LIVE_PROFILE_VERIFIED
#define G3R_LIVE_PROFILE_VERIFIED 1U
#endif
#ifndef G3R_CELL_LOW_CODE
#define G3R_CELL_LOW_CODE 38365U
#endif
#ifndef G3R_CELL_HIGH_CODE
#define G3R_CELL_HIGH_CODE 39372U
#endif
#define G3R_BASE_LOW_CODE 8958U
#define G3R_BASE_HIGH_CODE 9042U
#define G3R_PROFILE_ID "relay-exploration-20261101-r2"
#define G3R_FIRMWARE "g03-relay-r2"
#endif
''',encoding='utf-8')
port=root/'BMS_EXv1.1/BMS_EX/BSP/g03_relay_port.c';s=port.read_text()
s=s.replace('if(bits())G3R_Trip(&core,G3R_INTERLOCK,working.done_ms);','if(core.live && (core.base_min<G3R_BASE_LOW_CODE || core.base_max>G3R_BASE_HIGH_CODE))\n            G3R_Trip(&core,G3R_BASE,working.done_ms);\n        else if(bits())G3R_Trip(&core,G3R_INTERLOCK,working.done_ms);')
port.write_text(s,encoding='utf-8')
test=root/'tests/g03/test_relay_port.c';s=test.read_text()
s=s.replace('static unsigned afe_fault,spi_stall;','static unsigned afe_fault,spi_stall,afe_raw=9000;')
s=s.replace('i<3?38900:9000','i<3?38900:afe_raw')
s=s.replace('    send(4,32,0);run_until(G3R_PULSE,1500);','    afe_raw=9200;G03_RelayCommand(32,0);run_until(G3R_FAULT,1800);\n    assert(relay_field(3)&G3R_BASE);assert_off();assert(relay_field(19)==0);\n    afe_raw=9000;G03_RelayCommand(35,0);\n    send(4,32,0);run_until(G3R_PULSE,1500);')
# The disabled register fixture must explicitly override the live-capable profile.
test.write_text(s,encoding='utf-8')
checks=root/'scripts/g03/run_relay_checks.py';s=checks.read_text().replace("('disabled',[])","('disabled',['-DG3R_LIVE_PROFILE_VERIFIED=0'])")
checks.write_text(s,encoding='utf-8')
build=Path(__file__).parent/'build-relay.ps1'
(root/'build-relay.ps1').write_text(build.read_text().replace('20261101-G03-relay-r1','20261101-G03-relay-r2'),encoding='utf-8')
run=root/'evidence/runs/20261101-G03-relay-r2';run.mkdir(parents=True)
shutil.copy2(__file__,run/'prepare-live-r2.py')
print(root)
