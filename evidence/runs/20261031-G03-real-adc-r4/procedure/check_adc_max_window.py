from pathlib import Path
import json,sys,time
root=Path('D:/ADMIN/Desktop/WEIJI/zonghe');out=root/'evidence/runs/20261031-G03-real-adc-r4/max-window';out.mkdir(exist_ok=False)
sys.path.insert(0,str(root/'scripts/g03'))
from adc_diagnostics import Session,ok,dump,require
import serial
link=serial.Serial();link.port='COM9';link.baudrate=115200;link.timeout=.05;link.write_timeout=1;link.dtr=link.rts=False
s=Session(link,out);result={}
try:
    link.open();r=ok(s.request(20));s.identified=True
    require(r['state']==r['configured']==r['owns_adc']==0,'Initial idle/unconfigured')
    result['baseline']=ok(s.request(21,5));ok(s.request(22));ok(s.request(24,2000))
    for i in range(8):time.sleep(.18);ok(s.request(25))
    time.sleep(.65);status,rows=dump(s,out,'max-2s')
    result['scan']=status;result['preflight']=ok(s.request(21,6))
    require(status['state']==status['faults']==status['overwritten']==0 and status['reason']==1,'Duration stop/trace')
    require(status['count']==2000 and status['written']==207,'Full 2 second capacity')
    require({x['ccr'] for x in rows if x['event'] in (1,3)}=={1800,1700,1600,1500,1400},'Five shadow points')
    ok(s.request(26));ok(s.request(27));result['final']=ok(s.request(20))
    require(result['final']['configured']==result['final']['owns_adc']==result['final']['state']==result['final']['actual_bits']==0,'Final idle')
    result['checks']='passed'
except Exception as e:
    result.update(checks='failed',error=repr(e))
    if s.identified:
        result['stop']=s.request(26)
        result['fault_trace'],_=dump(s,out,'failed')
finally:
    s.finish();(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('baseline','preflight')},indent=2))
