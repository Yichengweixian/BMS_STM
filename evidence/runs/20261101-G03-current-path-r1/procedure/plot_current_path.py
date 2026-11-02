from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

run=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe\evidence/runs/20261101-G03-current-path-r1')
rows=list(csv.DictReader((run/'derived/samples.csv').open()))
fig,axes=plt.subplots(3,1,figsize=(11,8.5),constrained_layout=True)
sets=[ [('current-before','PA1, 11.5 cycles (before)'),('current-long','PA1, 1499.5 cycles'),('restored-current','PA1, 11.5 cycles (restored)')],
       [('input-0','PA0 / CH0, 1499.5 cycles'),('input-11','PA10 / CH11, 1499.5 cycles'),('input-14','PA2 / CH14, 1499.5 cycles')],
       [('internal-vref','Internal VREF / CH17, 1499.5 cycles')]]
for ax,group in zip(axes,sets):
    for label,title in group:
        values=[r for r in rows if r['label']==label]
        ax.plot([int(r['sample_index']) for r in values],[int(r['raw']) for r in values],label=title,lw=1.3,marker='.',ms=3)
    ax.axvspan(0,15.5,color='#c0c4ca',alpha=.25)
    ax.set_ylabel('ADC raw code');ax.set_xlim(0,63);ax.grid(alpha=.22)
    ax.legend(loc='best',fontsize=9)
axes[-1].set_xlabel('Sample index within each independent 64-value burst (not elapsed time)')
fig.suptitle('Disabled ADC input comparison — relay-r2\nFirst 16 values shaded; uncalibrated raw values, physical_valid = 0',fontsize=13)
fig.savefig(run/'derived/adc-input-comparison.png',dpi=170)
plt.close(fig)
print(run/'derived/adc-input-comparison.png')
