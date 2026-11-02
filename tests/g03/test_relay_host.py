import unittest,sys,binascii
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/g03'))
import relay_capture as r
def wire(body):
    b=body.encode();return b+b'*%04X\n'%binascii.crc_hqx(b,65535)
class Tests(unittest.TestCase):
    def test_status_crc_shape_and_output(self):
        v=[0]*len(r.STATUS);v[0]=1;v[17]=800000000
        body='#G3R,g03-relay-r2,'+','.join(map(str,v))
        self.assertEqual(r.parse(wire(body))['cpu_hz'],800000000)
        for bad in [wire(body)[:-4],wire(body.replace('relay-r2','bad-r2')),wire(body+',0')]:
            with self.assertRaises(ValueError):r.parse(bad)
        v[13]=1
        with self.assertRaises(ValueError):r.parse(wire('#G3R,g03-relay-r2,'+','.join(map(str,v))))
    def test_quality_not_zero(self):
        start=['1','0','0','3','1000','1010','16']
        samples=['1000','1007','0','4','1','0000000000000000']*5
        with self.assertRaises(ValueError):r.parse(wire('#G3S,g03-relay-r2,'+','.join(start+samples)))
    def test_window_coverage_and_recovery(self):
        s=dict(live=1,live_used=1,faults=0,state=5,on_ms=1000,off_ms=1099,on_cycles=100,off_cycles=79200100,cpu_hz=800000000,center=9000,tolerance=20)
        rows=[]
        def row(phase,start,value,end=None):
            return dict(phase=phase,at_ms=start,done_ms=end or start+8,samples=[dict(raw=value,raw_valid=1,start_ms=start,end_ms=end or start+7) for _ in range(5)])
        rows+=[row(2,900,9000)]
        rows+=[row(3,t,9500) for t in [1010,1030,1050,1070]]
        rows+=[row(3,1090,9500,1105)] # spans actual off: not counted
        rows+=[row(4,t,9000) for t in range(1120,1220,20)]
        a=r.analyze(s,rows);self.assertEqual(a['conclusion'],'response_and_recovery');self.assertEqual(a['valid_window_samples'],4)
        self.assertAlmostEqual(a['command_high_ms'],99)
        self.assertEqual(r.analyze(s,rows[:2])['conclusion'],'insufficient_observation')
        s['live']=0;self.assertEqual(r.analyze(s,rows)['conclusion'],'disabled_rehearsal_only')
        s['live']=1;s['faults']=1;self.assertEqual(r.analyze(s,rows)['conclusion'],'aborted')
        s['live_used']=0;self.assertIsNone(r.analyze(s,rows)['command_high_ms'])
    def test_no_change_is_not_missing(self):
        s=dict(live=1,faults=0,state=5,on_ms=0,off_ms=99,on_cycles=1,off_cycles=2,cpu_hz=800000000,center=9000,tolerance=20)
        rows=[dict(phase=3 if t<100 else 4,at_ms=t,done_ms=t+5,samples=[dict(raw=9000,raw_valid=1,start_ms=t,end_ms=t+5) for _ in range(5)]) for t in [10,30,50,120,140,160,180,200]]
        self.assertEqual(r.analyze(s,rows)['conclusion'],'no_clear_response')
        for row in rows[:3]:row['samples'][0]['raw_valid']=0
        self.assertEqual(r.analyze(s,rows)['conclusion'],'insufficient_observation')
if __name__=='__main__':unittest.main()
