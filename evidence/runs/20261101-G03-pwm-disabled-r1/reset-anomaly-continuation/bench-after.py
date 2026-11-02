"""Explicit disabled-only bench suite. Default prints a plan; --execute accesses hardware.

Each selected case gets exactly one independent warm SWD reset and one accepted
rehearsal start. A failure stops the suite; no reset/start retries or threshold
changes exist. Duplicate/conflicting frames and consumed-token starts are
explicit negative tests with separate event labels, never recovery attempts.
"""
import argparse
import csv
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
CLI = r'E:\ST\STM32CubeIDE_1.19.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.200.202503041107\tools\bin\STM32_Programmer_CLI.exe'
CONNECTION = [CLI, '-c', 'port=SWD', 'sn=16004A002933353739303541', 'freq=100', 'mode=HOTPLUG']
FIRMWARE = 'g03-pwm-disabled-r1'
CASES = [
    ('normal', 0, 100000, None),
    ('sample-6p5', 8, 100000, None),
    ('adc-stale', 1, 100000, None),
    ('adc-invalid', 2, 100000, None),
    ('fifo-overrun', 3, 100000, None),
    ('awd-low', 4, 100000, None),
    ('awd-high', 5, 100000, None),
    ('cache-full', 6, 100000, None),
    ('heartbeat-expiry', 7, 100000, None),
    ('explicit-stop', 0, 200000, 'stop'),
    ('foreground-stall', 0, 100000, 'stall'),
    ('bad-crc', 0, 200000, 'bad-crc'),
    ('rx-pressure', 0, 200000, 'rx-pressure'),
    ('duplicate-start', 0, 200000, 'duplicate'),
    ('conflicting-start', 0, 200000, 'conflict'),
]


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def insist(value, message):
    if not value:
        raise RuntimeError(message)


def reset_once(folder):
    command = CONNECTION + ['-rst']
    record = dict(command=command, started_utc=utc(), warm_reset_only=True, attempts=1)
    save(folder/'reset.json', record)
    try:
        result = subprocess.run(command, capture_output=True, timeout=25)
        (folder/'reset.stdout').write_bytes(result.stdout)
        (folder/'reset.stderr').write_bytes(result.stderr)
        record.update(exit_code=result.returncode, finished_utc=utc())
        text = result.stdout.decode(errors='replace')
        insist(result.returncode == 0 and 'Error:' not in text,
               'SWD reset failed; no repeated reset or start')
        record['completed'] = True
    except subprocess.TimeoutExpired as error:
        (folder/'reset.stdout').write_bytes(error.stdout or b'')
        (folder/'reset.stderr').write_bytes(error.stderr or b'')
        record['error'] = repr(error)
        raise
    finally:
        save(folder/'reset.json', record)
    # Explicit boot settling wait, not a polling loop or retry.
    time.sleep(2)


def write_test_bytes(session, wire, label):
    session.event(test_tx_hex=wire.hex(), negative_test=label)
    count = session.link.write(wire)
    session.event(test_tx_completed=label, bytes_written=count)
    insist(count == len(wire), 'Short test write; will not replay')


def consumed_start_negative(session, pwm, duration):
    """Only after a terminal, restored used=1 result; bypass client guard once."""
    status = session.last_status
    insist(status is not None and status['used'] == 1 and status['owned'] == 0 and
           status['timer_running'] == status['actual_bits'] == 0,
           'Consumed-token negative test requires proven stopped used state')
    insist(session.counter < 0xffffffff, 'Request ID exhausted')
    session.counter += 1
    request_id = session.counter
    session.sent[request_id] = (41, duration)
    write_test_bytes(session, pwm.frame(request_id, 41, duration), 'new-start-with-consumed-token')
    response = pwm.ok(session.receive(request_id), expected=4)
    insist(response['used'] == 1 and not response['timer_running'] and not response['actual_bits'],
           'Rejected start altered output/token state')
    return response


def verify_case(name, scenario, duration, action, status, rows, pwm):
    pwm.terminal(status)
    insist(status['run_us'] == duration and status['used'] == 1, 'Frozen run identity/window mismatch')
    insist((status['tim_hz'], status['adc_hz'], status['timer_hz']) == (400000000,64000000,1000000),
           'Unexpected runtime clocks')
    insist((status['arr'],status['ccr'],status['dtg']) == (2000,1000,0), 'Frozen disabled CCR/timer changed')
    insist(sum(r['event']==0 for r in rows) == 64, 'Missing preflight raw values')
    insist(sum(r['event']==1 for r in rows) == 1, 'Accepted start count is not exactly one')
    insist(any(r['event']==3 for r in rows), 'Missing register-off event')
    analysis = pwm.analyze(status, rows)
    preflight=[row for row in rows if row['event']==0]
    onset=next(row for row in rows if row['event']==1)
    analysis['preflight_first_to_last_us']=(preflight[-1]['us']-preflight[0]['us'])&0xffffffff
    analysis['preflight_last_to_start_us']=(onset['us']-preflight[-1]['us'])&0xffffffff
    analysis['preflight_first_to_start_us']=(onset['us']-preflight[0]['us'])&0xffffffff
    elapsed = analysis['observed_software_window_us']
    if action in ('stop','bad-crc','rx-pressure','conflict'):
        expected = 1 if action == 'stop' else 2
        insist(status['state']==pwm.FAULT and status['faults']==expected,
               'Expected STOP/protocol fault was not exclusively observed')
        insist(0 < elapsed < duration, 'Injected stop did not precede the local deadline')
    else:
        check = pwm.scenario_verdict(status, scenario)
        insist(check['verdict']=='pass', 'Scenario check failed: '+json.dumps(check))
    if scenario in (4,5):
        insist(any(r['event']==3 and r['flags']&0x80 for r in rows),
               'Real ADC AWD flag absent from off snapshot')
    if scenario==3:
        insist(any(r['event']==3 and r['flags']&0x10 for r in rows),
               'Real FIFO OVR flag absent from off snapshot')
    if scenario==1:
        age=(status['stop_us']-status['last_sample_us'])&0xffffffff
        insist(2000<=age<=2000+100+status['max_irq_gap_us'], 'Stale cutoff age mismatch')
    if scenario==7:
        insist(20000<=elapsed<=20000+100+status['max_irq_gap_us'], 'Heartbeat cutoff time mismatch')
    if action=='stall':
        lag=(status['now_us']-status['stop_us'])&0xffffffff
        insist(100000<=lag<0x80000000, 'Foreground stall did not outlast the local cutoff')
        analysis['foreground_cleanup_after_off_us']=lag
    return analysis


def run_case(index, case, out, args, pwm):
    name, scenario, duration, action = case
    folder=out/('%02d-'%index+name)
    folder.mkdir(exist_ok=False)
    data=dict(case=name,scenario=scenario,run_us=duration,action=action,
              evidence_scope=['bench'],verdict=None,started_utc=utc(),
              accepted_start_requests_planned=1,reset_attempts_planned=0 if index==1 and args.first_boot_evidence else 1,
              physical_valid=0,power_capable=0)
    save(folder/'manifest.json',dict(data,firmware=FIRMWARE,firmware_sha256=args.firmware_sha256,
                                   expected_boot='normal BOOT1=0 BOOT0=0',port=args.port))
    session=None
    rows=[]
    print('BEGIN '+name+' (one warm reset, disabled outputs)',flush=True)
    try:
        if index==1 and args.first_boot_evidence:
            # Explicit continuation from an independently queried unused boot.
            # Never entered automatically when reset_once fails.
            save(folder/'reset.json',dict(reset_performed=False,attempts=0,
                 independent_boot_evidence=str(args.first_boot_evidence),
                 basis='operator-reviewed query after reset API error; fresh wire state still required'))
        else:
            reset_once(folder)
        import serial
        link=serial.Serial()
        link.port,link.baudrate=args.port,115200
        link.timeout,link.write_timeout=.05,1
        link.dtr=link.rts=False
        session=pwm.Session(link,folder)
        link.open()
        initial=pwm.ok(session.request(40))
        data['initial']=initial
        insist(initial['firmware']==FIRMWARE and initial['state']==pwm.IDLE and
               initial['used']==initial['owned']==initial['faults']==initial['actual_bits']==initial['timer_running']==0,
               'Default disabled/unused state not confirmed; no start')
        data['power_command_rejected']=pwm.ok(session.request(49),expected=4)
        pwm.ok(session.request(46,scenario))
        start_id=session.send(41,duration)
        data['start_write_completed_monotonic']=time.monotonic()
        data['start_request_id']=start_id
        expected_reply=0
        wanted=start_id
        if action:
            # Default HAL_Delay(0) waits for the next 1 kHz tick. The 64 calls
            # take approximately 63--64 ms plus setup/IRQ latency, not a proven
            # host-to-arm upper bound. Keep this frozen 90 ms placement and
            # validate the actual preflight/on/off trace; never auto-retime/retry.
            time.sleep(.09)
            data['action_begin_monotonic']=time.monotonic()
            data['host_action_delay_s']=data['action_begin_monotonic']-data['start_write_completed_monotonic']
            if action=='stop':
                wanted=session.send(43)
            elif action=='stall':
                wanted=session.send(47,250000)
            elif action=='duplicate':
                write_test_bytes(session,pwm.frame(start_id,41,duration),'identical-start-request')
            elif action=='conflict':
                write_test_bytes(session,pwm.frame(start_id,41,duration-1),'conflicting-start-request')
                expected_reply=8
            elif action=='bad-crc':
                session.counter+=1
                body=pwm.frame(session.counter,40)
                wrong=b'0000' if body[-5:-1]!=b'0000' else b'FFFF'
                write_test_bytes(session,body[:-5]+wrong+b'\n','invalid-crc')
                time.sleep(.02)
                wanted=session.send(40)
            elif action=='rx-pressure':
                write_test_bytes(session,b'X'*512+b'\n','uart-pressure-512-bytes')
                time.sleep(.08) # let UART deliver/resynchronize; no second start
                write_test_bytes(session,b'\n','line-resynchronization')
                wanted=session.send(40)
        reply=pwm.ok(session.receive(wanted),expected=expected_reply)
        data['terminal_reply']=reply
        status=pwm.ok(session.request(40))
        data['terminal_status']=status
        insist(status['start_id']==start_id,'Terminal status belongs to another run')
        # A cleanup failure is terminal and its stable rows remain readable.
        rows=pwm.read_records(session,status)
        data['analysis']=pwm.analyze(status,rows)
        data['analysis']=verify_case(name,scenario,duration,action,status,rows,pwm)
        data['rejected_second_start']=consumed_start_negative(session,pwm,duration)
        clear=pwm.ok(session.request(44),expected=0 if status['state']==pwm.FAULT else 1)
        insist(clear['used']==1 and not clear['owned'] and not clear['actual_bits'],
               'Clear restored the once-per-boot token or output')
        data['clear']=clear
        data['rejected_start_after_clear']=consumed_start_negative(session,pwm,duration)
        data['final']=pwm.ok(session.request(40))
        data['verdict']='pass'
    except Exception as error:
        data['verdict']='fail'
        data['error']=repr(error)
        if session is not None and session.identified:
            try:
                data['stop_after_error']=session.request(43)
                failure_status=pwm.ok(session.request(40))
                data['status_after_error']=failure_status
                if not rows and failure_status['used'] and failure_status['state'] in (pwm.DONE,pwm.FAULT):
                    rows=pwm.read_records(session,failure_status)
                    data['failure_analysis']=pwm.analyze(failure_status,rows)
            except Exception as stop_error:
                data['stop_or_read_error']=repr(stop_error)
    finally:
        if session is not None:
            session.close()
        save(folder/'trace.json',rows)
        with (folder/'trace.csv').open('x',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=['firmware','kind']+pwm.TRACE)
            writer.writeheader();writer.writerows(rows)
        data['finished_utc']=utc()
        data['sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
        save(folder/'result.json',data)
        print(json.dumps(dict(case=name,verdict=data['verdict'],error=data.get('error'),
                             state=data.get('terminal_status',{}).get('state'),
                             faults=data.get('terminal_status',{}).get('faults'),
                             samples=data.get('terminal_status',{}).get('sample_count'))),flush=True)
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true',help='perform the reviewed disabled bench plan')
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--out',type=Path,default=ROOT/'evidence/runs/20261101-G03-pwm-disabled-r1/board-suite-01')
    parser.add_argument('--port',default='COM11')
    parser.add_argument('--firmware-sha256')
    parser.add_argument('--cases',help='comma-separated explicit subset; default all cases')
    parser.add_argument('--first-boot-evidence',type=Path,
                        help='explicit prior query result proving unused boot; skip first reset only')
    args=parser.parse_args()
    chosen=CASES
    if args.cases:
        names=args.cases.split(',')
        by_name={case[0]:case for case in CASES}
        if len(names)!=len(set(names)) or any(name not in by_name for name in names):
            parser.error('Unknown or duplicated case name')
        chosen=[by_name[name] for name in names]
    if not args.execute:
        print(json.dumps(dict(executed=False,plan=chosen,reset_command=CONNECTION+['-rst'],
                              hardware_requires_explicit_execute=True),indent=2))
        return 0
    if not args.firmware_sha256 or not re.fullmatch('[0-9a-fA-F]{64}',args.firmware_sha256):
        parser.error('--execute requires verified --firmware-sha256')
    if args.first_boot_evidence:
        evidence=json.loads(args.first_boot_evidence.read_text(encoding='utf-8'))
        previous=evidence.get('final',{})
        insist(evidence.get('data_integrity')=='pass' and not evidence.get('trigger_sent') and
               previous.get('firmware')==FIRMWARE and
               all(previous.get(k)==0 for k in ('state','used','owned','faults','actual_bits','timer_running')),
               'First boot evidence must be a valid query of unused, default disabled firmware')
    args.out.mkdir(parents=True,exist_ok=False)
    (args.out/'procedure.py').write_bytes(Path(__file__).read_bytes())
    manifest=dict(created_utc=utc(),firmware=FIRMWARE,firmware_sha256=args.firmware_sha256,
                  cases=chosen,evidence_scope=['bench'],physical_valid=0,power_capable=0,
                  one_independent_boot_per_case=True,
                  first_boot_evidence=str(args.first_boot_evidence) if args.first_boot_evidence else None,
                  reset_retries=0,start_retries=0,
                  flash_performed=False,real_power_operation=False,
                  scenario3='ADC NVIC masked for 200 us after 5 ms to create real FIFO overrun; no running IER write',
                  cleanup_failure='FAULT may retain owned=1; stopped stable trace is saved and suite fails',
                  trace_flags='event2/event3 ADC ISR bits; event4 core fault mask',
                  action_delay_s=.09,
                  preflight_timing_basis='64 HAL_Delay(0) calls at default 1 kHz: nominal 63--64 ms plus setup/IRQ latency; not a host-to-arm bound',
                  action_timing_method='Fixed host delay and saved timestamps; post-check MCU preflight/on/off trace; no automatic retiming',
                  max_electrical_on_time_claimed=False)
    save(args.out/'manifest.json',manifest)
    sys.path.insert(0,str(args.root/'scripts/g03'))
    import pwm_disabled as pwm
    results=[]
    for index,case in enumerate(chosen,1):
        result=run_case(index,case,args.out,args,pwm)
        results.append(dict(case=case[0],verdict=result['verdict'],error=result.get('error')))
        save(args.out/'progress.json',results)
        if result['verdict']!='pass':
            break
    summary=dict(planned=len(chosen),executed=len(results),results=results,
                 verdict='pass' if len(results)==len(chosen) and all(r['verdict']=='pass' for r in results) else 'fail',
                 finished_utc=utc(),physical_valid=0,power_output_tested=False,
                 warm_reset_evidence_only=True)
    save(args.out/'summary.json',summary)
    print(json.dumps(summary,indent=2),flush=True)
    return 0 if summary['verdict']=='pass' else 1


if __name__=='__main__':
    raise SystemExit(main())
