from pathlib import Path
import json,subprocess,re,sys
root=Path('D:/ADMIN/Desktop/WEIJI/zonghe');out=root/'evidence/runs/20261031-G03-real-adc-r4/internal-reference-probe'
out.mkdir(exist_ok=False)
old=json.loads((root/'evidence/runs/20261031-G03-disabled/flash-result-01.json').read_text())
conn=[old['command'][0],'-c','port=SWD','sn=16004A002933353739303541','freq=100','mode=HOTPLUG']
sys.path.insert(0,str(root/'scripts/g03'))
from adc_diagnostics import Session,ok
import serial
def link_session(folder):
    folder.mkdir();link=serial.Serial();link.port='COM9';link.baudrate=115200;link.timeout=.05;link.write_timeout=1;link.dtr=link.rts=False
    s=Session(link,folder);link.open();ok(s.request(20));s.identified=True;return s
def command(name,args):
    r=subprocess.run(conn+args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
    assert r.returncode==0,(name,r.stdout[-500:]);return r.stdout.decode(errors='replace')
def read(name,address):
    t=command(name,['-r32',hex(address),'4'])
    m=re.search('0x%08X'%address+r'\s*:\s*([0-9A-F]{8})',t,re.I);assert m,t
    return int(m[1],16)
s=link_session(out/'before-uart')
try:ok(s.request(26));ok(s.request(27))
finally:s.finish()
saved={};changed=False
try:
    command('halt',['-halt']);cr=read('cr',0x50022008);assert cr&5==0,cr
    for a in (0x50022030,0x50022018,0x5002201c,0x50022308):saved[a]=read('before-%x'%a,a)
    adc_or=read('option-register',0x500220d0)
    override={0x50022030:(saved[0x50022030]&~(31<<6))|(17<<6),0x50022018:saved[0x50022018]|(7<<21),0x5002201c:1<<17,0x50022308:saved[0x50022308]|(1<<22)}
    (out/'manifest.json').write_text(json.dumps(dict(firmware='g03-adc-r4',channel='ADC1 internal VREFINT channel17',external_channel_data_during_override_invalid=True,sampling_cycles=1499.5,saved=saved,override=override,adc_or=adc_or,no_OTP_write=True,no_VREFBUF_output_enable=True,no_power_enable=True),indent=2))
    changed=True
    for a,v in override.items():command('override-%x'%a,['-w32',hex(a),hex(v)]);assert read('override-check-%x'%a,a)==v
    command('resume-internal',['-run'])
    s=link_session(out/'internal-uart')
    try:
        for profile in (4,5):
            d=ok(s.request(21,profile));print(json.dumps(dict(profile=profile,minimum=d['minimum'],maximum=d['maximum'],tail_mean=sum(d['samples'][16:])/48,registers={k:d[k] for k in ('sqr1','pcsel','common_ccr')})))
    finally:s.finish()
finally:
    if changed:
        command('restore-halt',['-halt']);assert read('restore-cr',0x50022008)&5==0
        for a,v in saved.items():command('restore-%x'%a,['-w32',hex(a),hex(v)]);assert read('restore-check-%x'%a,a)==v
    command('restore-run',['-run'])
s=link_session(out/'restored-uart')
try:
    d=ok(s.request(21,5));ok(s.request(27));r=ok(s.request(20))
    assert d['sqr1']==64 and d['pcsel']==2 and d['common_ccr']==saved[0x50022308]
    assert r['state']==r['configured']==r['owns_adc']==r['actual_bits']==0
    (out/'result.json').write_text(json.dumps(dict(restored=True,external_diagnostic=d,final=r),indent=2));print('restored external channel and left unconfigured')
finally:s.finish()
