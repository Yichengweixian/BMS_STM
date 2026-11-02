"""Render an existing captured run; never synthesize absent measurements."""
import argparse,json
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument('run');a=p.parse_args();root=Path(a.run)
    rows=json.loads((root/'samples.json').read_text(encoding='utf-8'))
    result=json.loads((root/'result.json').read_text(encoding='utf-8'))
    if not rows:raise SystemExit('No captured samples to plot')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True,layout='constrained')
    origin=rows[0]['at_ms']
    for i,name in enumerate(['cell1','cell7','cell13','AFE GPIO1']):
        points=[(((r['samples'][i]['end_ms']-origin)&0xffffffff)/1000,r['samples'][i]['raw']) for r in rows if r['samples'][i]['raw_valid']]
        ax=axes[1] if i<3 else axes[0]
        if points:ax.plot(*zip(*points),marker='.',markersize=3,label=name)
    status=result.get('final',{})
    if status.get('base_count')==50:
        for ax in axes:
            for key in ['on_ms','off_ms']:ax.axvline(((status[key]-origin)&0xffffffff)/1000,color='gray',linestyle='--')
    axes[0].set_ylabel('AFE current raw code');axes[1].set_ylabel('Cell raw code');axes[1].set_xlabel('Device sample time (s)')
    for ax in axes:ax.grid(alpha=.3);ax.legend()
    fig.suptitle(root.name+' | '+result['mode']+' | uncalibrated raw data')
    path=root/'response.png'
    if path.exists():raise SystemExit('Plot already exists; use a new derived revision')
    fig.savefig(path,dpi=160);print(path)
if __name__=='__main__':main()
