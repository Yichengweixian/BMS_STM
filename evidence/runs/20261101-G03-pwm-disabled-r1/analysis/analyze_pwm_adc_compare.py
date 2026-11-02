"""Offline comparison of existing disabled board evidence; never touches hardware."""
import argparse, csv, hashlib, json, statistics as st, sys
from pathlib import Path

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def stats(v):
    return dict(n=len(v),minimum=min(v),maximum=max(v),peak_to_peak=max(v)-min(v),
                mean=st.mean(v),median=st.median(v),population_sd=st.pstdev(v))

def delta(a,b):
    return (a-b)&0xffffffff

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe'))
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    run=args.root/'evidence/runs/20261101-G03-pwm-disabled-r1'
    sys.path.insert(0,str(args.root/'scripts/g03'))
    from pwm_disabled import parse
    inputs={}
    cases=[]
    for folder,cycles,scenario in [('01-normal',11.5,0),('02-sample-6p5',6.5,8)]:
        p=run/'board-suite-01'/folder
        result=json.loads((p/'result.json').read_text(encoding='utf-8'))
        manifest=json.loads((p/'manifest.json').read_text(encoding='utf-8'))
        rows=json.loads((p/'trace.json').read_text(encoding='utf-8'))
        for name,sha in result['sha256'].items():
            assert digest(p/name)==sha,f'Artifact hash mismatch: {folder}/{name}'
        for name in ('result.json','manifest.json','trace.json','serial.bin'):
            inputs[str((p/name).relative_to(run))]=digest(p/name)
        reports=[parse(line) for line in (p/'serial.bin').read_bytes().splitlines()
                 if line.startswith((b'#G3P,',b'#G3E,'))]
        assert [r for r in reports if r['kind']=='#G3E']==rows
        s=result['terminal_status']
        assert s in reports
        assert result['verdict']=='pass' and s['scenario']==scenario
        assert s['state']==3 and s['faults']==s['trace_overflow']==0
        assert s['actual_bits']==s['power_capable']==s['physical_valid']==0
        assert s['restored']==1 and s['owned']==s['timer_running']==0
        assert [r['seq'] for r in rows]==list(range(len(rows)))
        pre=[r for r in rows if r['event']==0]
        fast=[r for r in rows if r['event']==2]
        assert len(pre)==64 and len(fast)==163 and s['sample_count']==9999
        assert all(r['actual_bits']==0 for r in rows)
        assert all((r['flags']&(0x10|0x80))==0 for r in fast)
        groups=dict(preflight_all=pre,preflight_tail48=pre[16:],fast_first64=fast[:64],
                    fast_decimated99=fast[64:],fast_retained163=fast)
        cases.append(dict(case=folder,scenario=scenario,sampling_cycles_selected=cycles,
            firmware_sha256=manifest['firmware_sha256'],status=s,
            stats={k:stats([r['raw'] for r in v]) for k,v in groups.items()},
            software_window_us=delta(s['stop_us'],s['start_us']),
            preflight_span_us=delta(pre[-1]['us'],pre[0]['us']),
            preflight_to_start_us=delta(s['start_us'],pre[0]['us']),
            preflight_gaps_us=stats([delta(b['us'],a['us']) for a,b in zip(pre,pre[1:])]),
            fast_first64_gaps_us=stats([delta(b['us'],a['us']) for a,b in zip(fast[:64],fast[1:64])]),
            decimated_gaps_us=stats([delta(b['us'],a['us']) for a,b in zip(fast[64:],fast[65:])]),
            first_fast_irq_offset_us=delta(fast[0]['us'],s['start_us']),pre=pre,fast=fast))
    assert cases[0]['firmware_sha256']==cases[1]['firmware_sha256']
    gpath=run/'resource-recovery-01/g01.csv'
    with gpath.open(encoding='utf-8-sig',newline='') as f:
        grows=list(csv.DictReader(f))
    mcu=[r for r in grows if r['channel']=='current_mcu_adc1' and r['phase']=='g01-15s']
    assert len(mcu)==30 and all(r['raw_valid']=='1' and r['physical_valid']=='0' for r in mcu)
    context=dict(source=str(gpath.relative_to(run)),raw=stats([int(r['raw']) for r in mcu]),
        start_interval_ms=stats([delta(int(b['start_ms']),int(a['start_ms'])) for a,b in zip(mcu,mcu[1:])]))
    inputs[str(gpath.relative_to(run))]=digest(gpath)
    args.out.mkdir(parents=True,exist_ok=False)
    out=args.out
    summary=dict(scope='disabled board evidence; no physical current calibration',physical_valid=0,
        firmware_sha256=cases[0]['firmware_sha256'],input_sha256=inputs,
        parser_sha256=digest(args.root/'scripts/g03/pwm_disabled.py'),
        cases=[{k:v for k,v in c.items() if k not in ('pre','fast')} for c in cases],
        regular_g01_context=context,
        statistics_note='Population SD describes retained codes only, not calibrated current noise. Full 9999-result means/SD are unavailable.')
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (out/'retained-samples.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f)
        w.writerow(['case','sampling_cycles_selected','phase','retained_index','sample_ordinal','timestamp_us','relative_us','raw','flags','actual_bits','physical_valid'])
        for c in cases:
            for i,r in enumerate(c['pre']):
                w.writerow([c['case'],c['sampling_cycles_selected'],'preflight',i,i+1,r['us'],delta(r['us'],c['pre'][0]['us']),r['raw'],r['flags'],0,0])
            for i,r in enumerate(c['fast']):
                ordinal=i+1 if i<64 else 64+(i-63)*100
                w.writerow([c['case'],c['sampling_cycles_selected'],'fast_first64' if i<64 else 'fast_decimated99',i,ordinal,r['us'],delta(r['us'],c['status']['start_us']),r['raw'],r['flags'],0,0])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(3,1,figsize=(10.5,10.2),layout='constrained')
    for c,color,marker in zip(cases,['#0068A5','#D46420'],['o','x']):
        label=f"{c['sampling_cycles_selected']:g} cycles"
        axes[0].plot([delta(r['us'],c['pre'][0]['us'])/1000 for r in c['pre']],[r['raw'] for r in c['pre']],color=color,marker=marker,ms=3,lw=1,alpha=.85,label=label)
        for ax,rows,scale in [(axes[1],c['fast'][:64],1),(axes[2],c['fast'][64:],1000)]:
            ax.plot([delta(r['us'],c['status']['start_us'])/scale for r in rows],[r['raw'] for r in rows],color=color,marker=marker,ms=3.5,lw=0,alpha=.8,label=label)
    titles=['A  Preflight: all 64 software-triggered codes per run',
        'B  Fast acquisition: first 64 consecutive retained results',
        'C  Fast acquisition: subsequent 99 retained results (every 100th result)']
    labels=['Time since first preflight observation (ms)','IRQ timestamp relative to run start (µs)','IRQ timestamp relative to run start (ms)']
    for ax,title,label in zip(axes,titles,labels):
        ax.set_title(title,loc='left',fontweight='bold')
        ax.set_xlabel(label);ax.set_ylabel('ADC raw code (LSB)')
        ax.grid(alpha=.22);ax.legend(loc='best',frameon=False)
    axes[0].set_ylim(1040,1440)
    axes[1].set_ylim(1258,1300);axes[2].set_ylim(1258,1300)
    fig.suptitle('Disabled acquisition comparison: 11.5 vs 6.5 sampling cycles\nOS2; 9,999 serviced results and 163 retained fast codes per run',fontsize=14,fontweight='bold')
    fig.supxlabel('Fast timestamps are ISR observations, not conversion durations. Outputs disabled; physical_valid = 0.',fontsize=10)
    fig.savefig(out/'adc-mode-comparison.png',dpi=180)
    fig.savefig(out/'adc-mode-comparison.svg')
    plt.close(fig)
    a,b=cases
    lines=['# 禁能 PWM 采集：11.5 / 6.5 cycles 对照','',
        '本次两个独立启动均完成 100 ms 禁能采集并恢复资源。两组快速采集原码分布接近；将采样时间从 11.5 改为 6.5 cycles，没有消除快速采集与预采集、常规 G01 采集之间的原码水平差异。','',
        '| 项目 | 11.5 cycles（scenario 0） | 6.5 cycles（scenario 8） |','|---|---:|---:|']
    for title,key in [('已服务 ADC 输出结果','sample_count'),('全结果原码下限','raw_min'),('全结果原码上限','raw_max'),('固件记录最大采样 IRQ 间隔 / µs','max_sample_gap_us'),('截止检查最大 IRQ 间隔 / µs','max_irq_gap_us')]:
        lines.append(f"| {title} | {a['status'][key]} | {b['status'][key]} |")
    lines += [f"| start/stop 软件时间差 / µs | {a['software_window_us']} | {b['software_window_us']} |",
        f"| 首条 preflight 至 start / µs | {a['preflight_to_start_us']} | {b['preflight_to_start_us']} |",
        '| preflight 保留数 / fast 保留数 | 64 / 163 | 64 / 163 |','',
        '下表均为所保留原码的描述统计；标准差采用总体标准差，单位为 ADC LSB。preflight 后 48 点单列以展示启动后的水平，全部 64 点仍保留在数据和图中。','',
        '| 原码区间 | 11.5 cycles：均值 / SD / 最小–最大 | 6.5 cycles：均值 / SD / 最小–最大 |','|---|---:|---:|']
    for label,key in [('preflight 全部 64 点','preflight_all'),('preflight 后 48 点','preflight_tail48'),('fast 首 64 点','fast_first64'),('fast 后续抽样 99 点','fast_decimated99')]:
        def fmt(c):
            s=c['stats'][key]
            return f"{s['mean']:.3f} / {s['population_sd']:.3f} / {s['minimum']}–{s['maximum']}"
        lines.append(f'| {label} | {fmt(a)} | {fmt(b)} |')
    ds=b['stats']['fast_decimated99']['mean']-a['stats']['fast_decimated99']['mean']
    g=context['raw']
    lines += ['',f"后续 99 点抽样均值差（6.5 − 11.5）为 {ds:.3f} LSB。本次各只有一个独立运行，不能据此建立重复性或确定哪一种采样时间更准确。",'',
        f"同轮资源恢复后的常规 G01 MCU 电流通道 30 点原码为 {g['minimum']}–{g['maximum']}，均值 {g['mean']:.3f} LSB，记录开始时间间隔为 {context['start_interval_ms']['minimum']}–{context['start_interval_ms']['maximum']} ms。它与本次 preflight/fast 的采样配置、触发方式、运行时间不同，只作为现象背景；不能把差值归结为节拍的唯一因果，也不能换算为实际放电电流。",'',
        '证据口径：','',
        '- 每组服务 9,999 个 OS2 ADC 输出结果；它不是 9,999 份已上传原码，也不是内部单次转换的数量。fast 原码仅保留前 64 点，随后每 100 点保留一条，共 163 条。全结果均值和标准差无法从抽取轨迹恢复；状态极值覆盖全部已服务结果。',
        '- fast 时间戳在 ISR 观测时记录；preflight 在轮询读取结果后记录。图上间隔、软件 start/stop 差值和 IRQ 间隔不能代替转换开始/完成时间或电气关断时间。',
        '- 11.5 / 6.5 cycles 为场景选择对应的固件配置，状态协议没有独立回读 SMPR 寄存器。两组均为 ADC 64 MHz、TIM1 400 MHz、时间戳定时器 1 MHz，ARR=2000、CCR=1000、DTG=0。',
        '- 每条 trace 和已解析状态的 actual_bits=0；终态 DONE、faults=0、owned=0、restored=1、timer_running=0。power_capable=0、physical_valid=0。该结果仅覆盖禁能采集和本地截止，不构成 PWM 引脚、驱动、电气死区或真实放电验收。',
        '- 已复核 result 中全部工件 SHA-256；serial.bin 内 G3P/G3E 的 CRC、身份和禁能字段通过解析，原始报文中的 trace 与 trace.json 一致。','',
        '![ADC 原码及时间对照](adc-mode-comparison.png)','',
        '输入：[11.5 cycles 结果](../board-suite-01/01-normal/result.json)、[6.5 cycles 结果](../board-suite-01/02-sample-6p5/result.json)、[常规 G01 原始表](../resource-recovery-01/g01.csv)。派生工件：[统计与输入哈希](summary.json)、[保留样本](retained-samples.csv)。','',
        f"固件 SHA-256：{a['firmware_sha256']}。"]
    (out/'comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    derived={'analysis_script_sha256':digest(Path(__file__)),'artifact_sha256':{p.name:digest(p) for p in out.iterdir() if p.is_file()}}
    (out/'manifest.json').write_text(json.dumps(derived,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(out=str(out),cases=[dict(case=c['case'],statistics=c['stats']) for c in cases],regular_context=context),ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()

