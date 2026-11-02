"""Offline-only open-loop preparation. There is intentionally no serial executor."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def prerequisites(profile):
    """Return unresolved evidence/limits, never manufacture defaults or authorization."""
    missing=[]
    for name in ('cell_voltage_min_V','cell_voltage_max_V','charge_current_max_A',
                 'discharge_current_max_A','charge_temperature_min_C','charge_temperature_max_C',
                 'discharge_temperature_min_C','discharge_temperature_max_C',
                 'converter_voltage_max_V','converter_current_max_A','converter_power_max_W',
                 'load_power_continuous_W','supply_current_limit_A'):
        if not finite(profile.get('limits',{}).get(name)):
            missing.append('limits.'+name)
    control=profile.get('control',{})
    for name in ('permitted_test_duty_min','permitted_test_duty_max','stop_delay_limit_us',
                 'effective_deadtime_min_ns','open_loop_point_max_ms','communication_timeout_ms'):
        if not finite(control.get(name)):
            missing.append('control.'+name)
    for name in ('relay_change_conditions','communication_loss_action','default_power_disabled_verified_run_id'):
        if not control.get(name):missing.append('control.'+name)
    # These are evidence gaps, not booleans a plan file can use to enable hardware.
    missing.extend(['verified pin/driver/Vgs waveforms and stop response',
                    'calibrated battery-branch current and voltage with sign/range',
                    'confirmed direction-specific wiring, energy sink, load and thermal conditions',
                    'MCU-local powered-mode interlocks, communication timeout and protection integration'])
    return missing


def compile_plan(plan, profile):
    if plan.get('direction') not in ('charge','discharge'):
        raise ValueError('direction must be charge or discharge')
    if plan.get('mode')!='fixed-duty':raise ValueError('fixed-duty mode required')
    control=profile.get('control',{})
    low,high=control.get('permitted_test_duty_min'),control.get('permitted_test_duty_max')
    limit=control.get('open_loop_point_max_ms')
    if not all(finite(x) for x in (low,high,limit)) or not 0<low<=high<1 or limit<=0:
        raise ValueError('Unknown/invalid permitted duty or duration in hardware profile')
    arr=profile.get('software_configuration',{}).get('pwm',{}).get('period')
    if type(arr) is not int or arr<2:raise ValueError('Profile must provide integer PWM arr')
    points=plan.get('points')
    if not isinstance(points,list) or not points or len(points)>1000:
        raise ValueError('Require 1..1000 fixed points')
    compiled=[];elapsed=0
    for p in points:
        duty,duration=p.get('duty'),p.get('duration_ms')
        if not finite(duty) or not low<=duty<=high:raise ValueError('Duty outside confirmed interval')
        if type(duration) is not int or not 0<duration<=limit:raise ValueError('Duration outside confirmed interval')
        ccr=int(math.floor(duty*arr+.5));actual=ccr/arr
        if not 0<ccr<arr or not low<=actual<=high:raise ValueError('Quantized duty outside confirmed interval')
        compiled.append(dict(index=len(compiled),at_ms=elapsed,duration_ms=duration,
                             requested_duty=duty,ccr=ccr,quantized_duty=actual))
        elapsed+=duration
        if elapsed>0x7fffffff:raise ValueError('Schedule duration exceeds unambiguous tick interval')
    return dict(direction=plan['direction'],points=compiled,stop_at_ms=elapsed)


def simulate(compiled, stop_at_ms=None, fault_at_ms=None):
    """Discrete software sequence only; does not model the converter or measured current."""
    end=compiled['stop_at_ms'];reason='schedule_end'
    for t,label in ((stop_at_ms,'STOP'),(fault_at_ms,'latched_fault')):
        if t is not None:
            if type(t) is not int or t<0:raise ValueError('Invalid injected event time')
            if t<=end:end=t;reason=label
    events=[dict(at_ms=p['at_ms'],event='apply_fixed_ccr',ccr=p['ccr'])
            for p in compiled['points'] if p['at_ms']<end]
    events.append(dict(at_ms=end,event=reason,output_enabled=False))
    return dict(simulated=True,physical_model=False,events=events,
                final_state='FAULT' if reason=='latched_fault' else 'STOPPED',
                output_enabled=False,automatic_restart=False)


def port_power(voltage, current, max_skew_ms):
    """Only calibrated, same-port, same-session samples with explicit sign conventions."""
    if not finite(max_skew_ms) or max_skew_ms<0:raise ValueError('Invalid alignment tolerance')
    for sample,unit in ((voltage,'V'),(current,'A')):
        if sample.get('physical_valid') is not True or not sample.get('cal_id'):
            raise ValueError('Calibrated valid physical sample required')
        if sample.get('unit')!=unit or not finite(sample.get('value')) or not finite(sample.get('time_ms')):
            raise ValueError('Invalid physical value/unit/time')
        if not sample.get('session_id') or not sample.get('port') or not sample.get('reference'):
            raise ValueError('Missing session/port/reference')
    if voltage['session_id']!=current['session_id'] or voltage['port']!=current['port']:
        raise ValueError('Cannot multiply different sessions or ports')
    if abs(voltage['time_ms']-current['time_ms'])>max_skew_ms:raise ValueError('Unaligned samples')
    power=voltage['value']*current['value']
    if not finite(power):raise ValueError('Power overflow')
    return dict(port=voltage['port'],value=power,unit='W',
                voltage_reference=voltage['reference'],current_reference=current['reference'],
                session_id=voltage['session_id'],cal_ids=[voltage['cal_id'],current['cal_id']])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',required=True);p.add_argument('--plan',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    profile=json.loads(Path(a.profile).read_text(encoding='utf-8-sig'))
    plan=json.loads(Path(a.plan).read_text(encoding='utf-8-sig'))
    result=dict(evidence_scope=['static'],verdict=None,power_execution_available=False,
                missing=prerequisites(profile),input_sha256={str(x):hashlib.sha256(x.read_bytes()).hexdigest()
                    for x in (Path(a.profile),Path(a.plan),Path(__file__))})
    try:
        result['compiled']=compile_plan(plan,profile)
        result['simulation']=simulate(result['compiled'])
        result['evidence_scope'].append('simulation')
    except (ValueError,TypeError,KeyError) as exc:result['plan_error']=str(exc)
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return 0 # Producing a missing-input report is a successful offline action, never authorization.


if __name__=='__main__':raise SystemExit(main())
