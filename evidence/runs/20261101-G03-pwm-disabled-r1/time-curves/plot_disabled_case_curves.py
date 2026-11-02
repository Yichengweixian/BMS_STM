"""Generate per-run curves from saved disabled-only evidence; no hardware access."""
import argparse, csv, hashlib, json, sys
from pathlib import Path

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rel(us,start):
    return ((us-start+0x80000000)&0xffffffff)-0x80000000

FAULTS={0:'STOP',1:'protocol',2:'invalid',3:'stale',4:'OVR',5:'AWD',6:'heartbeat',
        7:'late_ISR',8:'adapter',16:'cache_full',17:'interlock'}
EVENTS={1:('start','#2C7C4E','-'),3:('off','#D06022','--'),
        4:('fault record','#BD254C',':'),5:('cleanup','#6E4AA2','-.')}

def reason(mask):
    return '+'.join(name for bit,name in FAULTS.items() if mask&(1<<bit)) or 'deadline'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe'))
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    root=args.root/'evidence/runs/20261101-G03-pwm-disabled-r1'
    sys.path.insert(0,str(args.root/'scripts/g03'))
    from pwm_disabled import parse
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,
        'axes.spines.top':False,'axes.spines.right':False,'svg.hashsalt':'g03-disabled-curves-r1'})
    paths=sorted(root.glob('board-suite-*/*/result.json'))
    runs=[];skipped=[];inputs={}
    for rp in paths:
        result=json.loads(rp.read_text(encoding='utf-8'))
        if result.get('verdict')!='pass':
            skipped.append(dict(path=str(rp.relative_to(root)),verdict=result.get('verdict')))
            continue
        folder=rp.parent
        trace=json.loads((folder/'trace.json').read_text(encoding='utf-8'))
        s=result['terminal_status']
        for name,expected in result['sha256'].items():
            assert sha(folder/name)==expected,(folder,name)
        for name in ('result.json','trace.json','serial.bin','manifest.json'):
            inputs[str((folder/name).relative_to(root))]=sha(folder/name)
        reports=[parse(line) for line in (folder/'serial.bin').read_bytes().splitlines()
            if line.startswith((b'#G3P,',b'#G3E,'))]
        assert [r for r in reports if r['kind']=='#G3E']==trace
        assert s in reports
        assert s['state'] in (3,4) and s['restored']==1 and s['owned']==s['timer_running']==0
        assert s['actual_bits']==s['physical_valid']==s['power_capable']==0
        assert all(r['actual_bits']==0 for r in trace)
        assert [r['seq'] for r in trace]==list(range(len(trace)))
        assert sum(r['event']==0 for r in trace)==64
        assert sum(r['event']==1 for r in trace)==1
        assert sum(r['event']==3 for r in trace)==1
        assert sum(r['event']==5 for r in trace)==1
        runs.append((folder,result,trace,s))
    assert len(runs)==15,len(runs)
    args.out.mkdir(parents=True,exist_ok=False)
    stoprows=[];index=[]
    for folder,result,trace,s in runs:
        name=f'{folder.parent.name}-{folder.name}'
        pre=[r for r in trace if r['event']==0]
        fast=[r for r in trace if r['event']==2]
        start=s['start_us']
        stop_us=rel(s['stop_us'],start)
        life=[r for r in trace if r['event'] in EVENTS]
        fig,axs=plt.subplots(3,1,figsize=(10.4,7.8),height_ratios=[2.2,1.8,.65],layout='constrained')
        ax,zoom,bits=axs
        ax.plot([rel(r['us'],start)/1000 for r in pre],[r['raw'] for r in pre],
            color='#0068A5',marker='o',ms=2.5,lw=.8,label=f'Preflight ({len(pre)})')
        if fast:
            xs=[rel(r['us'],start)/1000 for r in fast]
            ys=[r['raw'] for r in fast]
            ax.plot(xs,ys,color='#D46420',marker='.',ms=3,lw=0,label=f'Fast retained ({len(fast)})')
            zoom.plot(xs,ys,color='#D46420',marker='.',ms=3.5,lw=0)
            yrange=max(ys)-min(ys)
            zoom.set_ylim(min(ys)-max(2,yrange*.15),max(ys)+max(2,yrange*.15))
        else:
            ax.text(.98,.84,'No fast samples',transform=ax.transAxes,ha='right',
                color='#9F2439',fontweight='bold')
            zoom.text(.5,.5,'NO FAST SAMPLES\nAWD shutdown before a fast result was consumed',
                transform=zoom.transAxes,ha='center',va='center',color='#9F2439',fontsize=11)
            zoom.set_yticks([])
        ax.set_title('A  Saved raw codes across the complete run',loc='left',fontweight='bold')
        zoom.set_title('B  Fast acquisition interval (retained samples only)',loc='left',fontweight='bold')
        for row in life:
            label,color,style=EVENTS[row['event']]
            x=rel(row['us'],start)/1000
            ax.axvline(x,color=color,ls=style,lw=1,label=label)
            bits.axvline(x,color=color,ls=style,lw=1,alpha=.8)
            if x<=max(stop_us/1000*1.08,.025):
                zoom.axvline(x,color=color,ls=style,lw=1,alpha=.8)
        ax.legend(loc='best',ncol=3,fontsize=8,framealpha=.8)
        ax.set_ylabel('Raw ADC code (LSB)');zoom.set_ylabel('Raw ADC code (LSB)')
        zoom.set_xlim(-max(stop_us/1000*.015,.001),max(stop_us/1000*1.08,.025))
        bits.plot([rel(r['us'],start)/1000 for r in trace],[r['actual_bits'] for r in trace],
            'o',color='#2C7C4E',ms=2)
        bits.set_ylim(-.15,1.1);bits.set_yticks([0,1]);bits.set_ylabel('Recorded\nactual_bits')
        bits.text(.99,.78,'All saved values = 0',transform=bits.transAxes,ha='right',color='#2C7C4E')
        bits.set_xlim(ax.get_xlim())
        for axis in axs:
            axis.set_xlabel('Timestamp relative to start (ms)')
            axis.grid(alpha=.18)
        conclusion=reason(s['faults'])
        fig.suptitle(f"{result['case']}  |  disabled board test passed\n"
            f"scenario {result['scenario']}; stop {stop_us/1000:.3f} ms ({conclusion}); "
            f"{s['sample_count']:,} serviced / {len(fast)} retained fast results",
            fontsize=12,fontweight='bold')
        fig.supxlabel('Fast times are ISR observations; fault marker is the logged fault event. No physical current calibration; physical_valid = 0.',fontsize=8)
        fig.savefig(args.out/(name+'.png'),dpi=160)
        plt.close(fig)
        common=dict(suite=folder.parent.name,case=folder.name,scenario=result['scenario'],
            start_id=s['start_id'],start_us=start,terminal_state=s['state'],
            faults=s['faults'],stop_reason=conclusion,sample_count=s['sample_count'],
            fast_retained=len(fast),trace_overflow=s['trace_overflow'],
            restored=s['restored'],physical_valid=0)
        stoprows.append(dict(**common,source='status',event='stop_us',seq='',
            timestamp_us=s['stop_us'],relative_us=stop_us,raw='',
            flags='',flags_meaning='',actual_bits=s['actual_bits']))
        for row in trace:
            if row['event']>=3:
                meaning={3:'ADC_ISR_bits',4:'core_fault_mask',5:'cleanup_flags'}[row['event']]
                stoprows.append(dict(**common,source='trace',event=EVENTS[row['event']][0],
                    seq=row['seq'],timestamp_us=row['us'],relative_us=rel(row['us'],start),
                    raw=row['raw'],flags=row['flags'],flags_meaning=meaning,actual_bits=row['actual_bits']))
        index.append(dict(**common,curve=name+'.png',source=str((folder/'result.json').relative_to(root))))
    with (args.out/'stop-events.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(stoprows[0]))
        writer.writeheader();writer.writerows(stoprows)
    manifest=dict(analysis_script_sha256=sha(Path(__file__)),input_sha256=inputs,
        parser_sha256=sha(args.root/'scripts/g03/pwm_disabled.py'),cases=index,
        excluded_unsuccessful_runs=skipped,
        notes=['Failed reset attempt is retained at its original path and is not a successful curve.',
               'No fast samples are plotted as missing, never zero.',
               'Off/fault/cleanup raw fields preserve the last code; they are not plotted as fresh samples.',
               'Trace is decimated except cache-full scenario; serviced counts do not imply all original codes were retained.',
               'GPIO/timer command bits are recorded software observations, not measured electrical outputs.'])
    manifest['artifact_sha256']={p.name:sha(p) for p in args.out.iterdir() if p.is_file()}
    (args.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(curves=len(index),stop_event_rows=len(stoprows),out=str(args.out),
        excluded=skipped),ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()

