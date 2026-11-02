"""Plot real, independently captured relay responses aligned to GPIO command time."""
import argparse,json,statistics
from pathlib import Path
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('comparison');p.add_argument('--out',required=True);a=p.parse_args()
    data=json.loads(Path(a.comparison).read_text(encoding='utf-8'));out=Path(a.out)
    if out.exists():raise SystemExit('Refuse to overwrite a plot')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(10,8),sharex=True,layout='constrained')
    for index,run in enumerate(data['runs'],1):
        path=Path(run['path']);rows=json.loads((path/'samples.json').read_text(encoding='utf-8'));st=json.loads((path/'result.json').read_text(encoding='utf-8'))['final']
        t=lambda v:(((v-st['on_ms']+0x80000000)&0xffffffff)-0x80000000)/1000
        for ax,i,ch in [(axes[0],3,'afe_current'),(axes[1],4,'mcu_current')]:
            base=run['channels'][ch]['baseline_median']
            pts=[(t(x['samples'][i]['end_ms']),x['samples'][i]['raw']-base) for x in rows if x['samples'][i]['raw_valid']]
            ax.plot(*zip(*pts),marker='.',markersize=3,label='Run '+str(index),alpha=.8)
        base=sum(run['channels'][ch]['baseline_median'] for ch in ['cell1','cell7','cell13'])
        pts=[(t(max(s['end_ms'] for s in x['samples'][:3])),sum(s['raw'] for s in x['samples'][:3])-base) for x in rows if all(s['raw_valid'] for s in x['samples'][:3])]
        axes[2].plot(*zip(*pts),marker='.',markersize=3,label='Run '+str(index),alpha=.8)
    for ax in axes:
        ax.axvspan(0,.099,color='gray',alpha=.12,label='99 ms command budget');ax.axhline(0,color='gray',linewidth=.6);ax.grid(alpha=.25);ax.legend(loc='lower right')
    axes[0].set_ylabel('AFE delta (raw codes)');axes[1].set_ylabel('MCU delta (raw codes)');axes[2].set_ylabel('Sum of cell deltas\n(raw codes)');axes[2].set_xlabel('Sample end time relative to PG5 command (s)')
    fig.suptitle('Three independent relay runs | unchanged conditions | physical_valid=0')
    fig.savefig(out,dpi=160);print(out)
if __name__=='__main__':main()
