import binascii
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/g02'))
from host_diagnostics import frame, parse, FIELDS
from extended_diagnostics import Session
from prepower_plan import compile_plan, simulate, port_power, prerequisites


def response(request_id=1,firmware='g02-host-r2',**values):
    fields=dict.fromkeys(FIELDS,0);fields.update(id=request_id,**values)
    body=('#G02,'+firmware+','+','.join(str(fields[k]) for k in FIELDS)).encode()
    return body+('*%04X\r\n'%binascii.crc_hqx(body,65535)).encode()


class FakeLink:
    def __init__(self,chunks):self.chunks=list(chunks);self.is_open=True;self.writes=[]
    @property
    def in_waiting(self):return len(self.chunks[0]) if self.chunks else 0
    def read(self,n):return self.chunks.pop(0) if self.chunks else b''
    def write(self,data):self.writes.append(data);return len(data)
    def close(self):self.is_open=False


class HostTests(unittest.TestCase):
    def session(self,chunks):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        link=FakeLink(chunks);s=Session(link,Path(tmp.name));self.addCleanup(s.finish)
        return s,link

    def test_crc_reference(self):
        self.assertEqual(binascii.crc_hqx(b'123456789',65535),0x29b1)
        self.assertEqual(parse(response())['id'],1)

    def test_unsigned_request_bounds(self):
        for args in ((0,0,0),(-1,0,0),(2**32,0,0),(1,0,-1),(True,0,0),(1,0,float('nan'))):
            with self.assertRaises(ValueError):frame(*args)

    def test_crc_schema_and_nonfinite_rejected(self):
        for data in (response().replace(b'g02-host-r2',b'g02-host-r9'),
                     response(result='NaN'),response(idont_exist=3).replace(b'*',b'*0'),
                     response(result=-1),response(result=2**32)):
            with self.assertRaises(ValueError):parse(data)

    def test_fragmented_coalesced_and_stale_responses(self):
        wire=b'#META,x\n'+response(4)+response(5)
        s,_=self.session([wire[:4],wire[4:20],wire[20:]])
        self.assertEqual(s.receive(5,.1)['id'],5)
        self.assertEqual(len(s.reports),2)

    def test_reboot_cancels_without_replay(self):
        s,link=self.session([b'#BOOT,new\n'+response()]);s.identified=True
        with self.assertRaisesRegex(RuntimeError,'reset'):s.receive(1,.1)
        self.assertEqual(link.writes,[])

    def test_wrong_firmware_and_output_gate(self):
        for wire in (response(firmware='g02-host-r1'),response(pins_gate=1)):
            s,_=self.session([wire])
            with self.assertRaises(RuntimeError):s.receive(1,.1)

    def test_timeout_does_not_retry(self):
        s,link=self.session([])
        with self.assertRaises(TimeoutError):s.receive(1,.001)
        self.assertEqual(link.writes,[])

    def test_oversized_stream_and_counter_exhaustion(self):
        s,link=self.session([b'x'*4097])
        with self.assertRaises(RuntimeError):s.receive(1,.1)
        s.counter=0xffffffff
        with self.assertRaises(RuntimeError):s.send(0)
        self.assertEqual(link.writes,[])


class PlanTests(unittest.TestCase):
    def setUp(self):
        # Fictional software fixture only, never copied into the real hardware profile.
        self.profile={'control':{'permitted_test_duty_min':.2,'permitted_test_duty_max':.8,'open_loop_point_max_ms':100},
                      'software_configuration':{'pwm':{'period':2000}}}
        self.plan={'mode':'fixed-duty','direction':'discharge','points':[
            {'duty':.4,'duration_ms':100},{'duty':.5,'duration_ms':100}]}
        self.v={'value':10.,'unit':'V','physical_valid':True,'cal_id':'synthetic-v',
                'session_id':'synthetic','port':'battery','time_ms':0,'reference':'positive_to_negative'}
        self.i=dict(self.v,value=-2.,unit='A',cal_id='synthetic-i',reference='positive_into_battery')

    def test_order_quantization_and_final_stop(self):
        c=compile_plan(self.plan,self.profile)
        self.assertEqual([p['ccr'] for p in c['points']],[800,1000])
        self.assertEqual([p['at_ms'] for p in c['points']],[0,100])
        r=simulate(c);self.assertEqual(r['events'][-1]['at_ms'],200)
        self.assertFalse(r['output_enabled'])

    def test_stop_fault_cancel_remaining_points(self):
        c=compile_plan(self.plan,self.profile)
        for when in (0,50,100,200):
            for key in ('stop_at_ms','fault_at_ms'):
                r=simulate(c,**{key:when})
                self.assertTrue(all(e['at_ms']<when for e in r['events'][:-1]))
                self.assertFalse(r['output_enabled']);self.assertFalse(r['automatic_restart'])

    def test_unknown_limits_not_course_defaults(self):
        actual=json.loads((ROOT/'instructions/specs/hardware-profile.json').read_text(encoding='utf-8-sig'))
        with self.assertRaises(ValueError):compile_plan(self.plan,actual)
        self.assertIn('control.permitted_test_duty_min',prerequisites(actual))

    def test_invalid_duty_duration_and_closed_loop(self):
        for duty in (None,float('nan'),float('inf'),-.1,1.0,True):
            p=copy.deepcopy(self.plan);p['points'][0]['duty']=duty
            with self.assertRaises(ValueError):compile_plan(p,self.profile)
        for duration in (0,-1,101,True,1.5):
            p=copy.deepcopy(self.plan);p['points'][0]['duration_ms']=duration
            with self.assertRaises(ValueError):compile_plan(p,self.profile)
        p=copy.deepcopy(self.plan);p['mode']='current-tracking'
        with self.assertRaises(ValueError):compile_plan(p,self.profile)

    def test_quantization_cannot_escape_limits(self):
        self.profile['control']['permitted_test_duty_min']=.4001
        self.plan['points'][0]['duty']=.4001
        with self.assertRaises(ValueError):compile_plan(self.plan,self.profile)

    def test_power_sign_and_quality(self):
        self.assertEqual(port_power(self.v,self.i,1)['value'],-20.)
        for key,value in (('port','load'),('session_id','other'),('physical_valid',False),
                          ('cal_id',None),('value',float('nan')),('time_ms',2),('unit','V'),('reference',None)):
            sample=dict(self.i,**{key:value})
            with self.assertRaises(ValueError):port_power(self.v,sample,1)


if __name__=='__main__':unittest.main()
