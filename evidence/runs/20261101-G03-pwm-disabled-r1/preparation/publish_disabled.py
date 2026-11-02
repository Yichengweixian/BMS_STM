from pathlib import Path
import datetime, hashlib, json, shutil, subprocess

STAGE=Path(__file__).parent
ROOT=Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
WORK=STAGE/'workspace'
RUN=ROOT/'evidence/runs/20261101-G03-pwm-disabled-r1'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def copy(a,b): b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)

old=json.loads((ROOT/'evidence/runs/20261101-G03-relay-r2/production-source-manifest.json').read_text())
assert all(digest(ROOT/x['path'])==x['sha256'] for x in old['files']), 'Root source changed since baseline; inspect before publishing'
checks=json.loads((STAGE/'pwm-checks-final/result.json').read_text())
assert checks['verdict']=='pass'
host_checks=json.loads((STAGE/'host-checks-final/result.json').read_text())
assert host_checks['verdict']=='pass'
tested={Path(p).as_posix():h for p,h in checks['source_sha256'].items()};tested.update(host_checks['source_sha256'])
assert all(digest(WORK/p)==h for p,h in tested.items()), 'Tested source differs'
production=sorted(p for p in (WORK/'BMS_EXv1.1/BMS_EX').rglob('*') if p.is_file() and p.suffix.lower() in ('.c','.h','.s','.sct','.uvprojx','.ioc'))
changes=[p for p in production if not (ROOT/p.relative_to(WORK)).exists() or digest(p)!=digest(ROOT/p.relative_to(WORK))]
extras=['scripts/g03/pwm_disabled.py','scripts/g03/run_pwm_checks.py','tests/g03/test_pwm_oneshot.c','tests/g03/test_pwm_port.c','tests/g03/pwm_port_fixture/main.h','tests/g03/test_pwm_disabled_host.py']
for rel in extras: assert (WORK/rel).is_file()
RUN.mkdir(parents=True,exist_ok=False)
(RUN/'git-status-before.txt').write_bytes(subprocess.check_output(['git','status','--short'],cwd=ROOT))
(RUN/'git-diff-before.patch').write_bytes(subprocess.check_output(['git','diff','--binary'],cwd=ROOT))
changed=[]
for src in changes+[WORK/p for p in extras]:
    rel=src.relative_to(WORK); dst=ROOT/rel
    before=digest(dst) if dst.exists() else None
    if dst.exists(): copy(dst,RUN/'before'/rel)
    copy(src,dst)
    changed.append(dict(path=rel.as_posix(),before_sha256=before,after_sha256=digest(dst)))
for src in production: copy(src,RUN/'source-after'/src.relative_to(WORK))
for rel in extras: copy(WORK/rel,RUN/'source-after'/rel)
firmware={}
for suffix in ('Debug','Release'):
    target='BMS_PWM_Disabled_'+suffix
    firmware[target]={}
    for ext in ('hex','axf','bin','map'):
        src=WORK/f'BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/{target}/{target}.{ext}'
        dst=RUN/'firmware'/target/src.name;copy(src,dst)
        firmware[target][ext]=dict(path=dst.relative_to(ROOT).as_posix(),sha256=digest(dst))
    copy(STAGE/f'{target}-build-final.log',RUN/'build'/f'{target}-build-final.log')
for name in ('build-debug-01.log','build-release-01.log','hex-followup.md','hex-followup-sources.json','port-review-first-pass.md','publish_disabled.py','integrate_sources.py','integrate_pwm_build.py'):
    copy(STAGE/name,RUN/'preparation'/name)
for name in ('pwm-checks-final','host-checks-final','regression-relay-01','regression-adc-01','core-validation','port-validation','build-integration'):
    shutil.copytree(STAGE/name,RUN/'offline'/name)
save(RUN/'production-source-manifest.json',dict(files=[dict(path=p.relative_to(WORK).as_posix(),sha256=digest(p)) for p in production],firmware=firmware,changes=changed,build_workspace=str(WORK)))
save(RUN/'manifest.json',dict(run_id=RUN.name,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),firmware_identity='g03-pwm-disabled-r1',status='in_progress',verdict=None,evidence_scope=['static','simulation','build'],physical_valid=0,power_capable=0,flash_verdict=None,bench_verdict=None,firmware=firmware,source_manifest='production-source-manifest.json',conditions=dict(tim1_hz=400000000,adc_hz=64000000,tim2_hz=1000000,arr=2000,ccr_shadow=1000,dtg=0,pwm_outputs_enabled=False,relays_enabled=False,periodic_irq_us=100,adc_max_age_us=2000,isr_max_gap_us=500,normal_run_us=100000,preflight_samples=64,normal_sampling_cycles=11.5,comparison_sampling_cycles=6.5),timestamp_scope='IRQ service observation; not a hardware conversion timestamp',fixture_scope='Synthetic verified facts/current limits exercise closed-output logic only; not verified physical parameters',build=dict(Release=dict(errors=0,warnings=0),Debug=dict(errors=0,warnings=1,warning='existing EXTRAM L6314W')),offline=dict(verdict='pass',core_groups=21,port_groups=15,host_tests=19,affected_legacy=['relay','adc'])))
(RUN/'work-card.md').write_text('''# G03 单次 PWM 禁能接入与板测

本次只运行定时器与真实 ADC，PA9/PF7 保持 GPIO 禁能，TIM1 MOE/CCER 和 PB5/PG5 均不允许开启。新增独立 Debug/Release target，原继电器 target 和镜像保留。

## 已完成的软件检查

微秒计时核心 21 组、实际 port 寄存器模型 15 组、主机 19 项及受影响继电器/ADC 回归通过。模型验证不代替板测。Release 0 错 0 警告；Debug 0 错、原有 EXTRAM 警告 1 条。完整源码、镜像和哈希见 production-source-manifest.json。

## 固定的禁能验证

运行身份 g03-pwm-disabled-r1；单次令牌；本地 TIM2 1MHz、100us IRQ 截止。普通演练 100ms，协议停止试验 200ms；样本年龄阈值 2000us，IRQ 最大间隔阈值 500us。阈值属于禁能软件夹具，不是电气通电限值。比较 ADC CH1 的 11.5 和老师 HEX 的 6.5 周期，保存预备 64 点、快速开头、抽取记录及全部停止事件。

每个已列场景仅一次独立软件复位和一次启动；失败立即记录并停止本轮，不重试或自动放宽判据。覆盖正常截止、采样过期/无效/FIFO溢出、双侧 AWD、缓存耗尽、心跳、STOP、前台阻塞、协议错误与请求重复/冲突。下载必须读回验证，正常 BOOT 后先确认身份和所有输出为0。

## 证据边界

fast ADC 时间是 IRQ 观察时间，不冒充硬件转换起止时间。physical_valid 恒0。fixture 的 verified_facts 和标称 mA 限值只测试关闭输出后的逻辑，不是实物证据。未使用老师 HEX 刷写，不执行真实 PWM/继电器放电；老师资料新增信息见 preparation/hex-followup.md。

当前下载与板测结果尚未产生，manifest 中保持 null。阶段进度统一维护于 instructions/STATUS.md。
''',encoding='utf-8')
save(RUN/'publication.json',dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),changed=changed,baseline_files_verified=len(old['files']),production_files=len(production),old_generated_cmse_object_preserved=True))
print(json.dumps(dict(run=str(RUN),changed=len(changed),production_files=len(production),release=firmware['BMS_PWM_Disabled_Release']['hex']),ensure_ascii=False))
