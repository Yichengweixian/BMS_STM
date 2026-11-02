from pathlib import Path
import hashlib,json,shutil,subprocess
root=Path(__file__).parent;original=Path('D:/ADMIN/Desktop/WEIJI/zonghe')
out=root/'evidence/runs/20261101-G03-relay-r1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((root/'baseline-manifest.json').read_text())
# Revert incidental line-ending-only rewrites in staging, after checking original identity.
for rel,h in baseline.items():
    p=root/rel;q=original/rel
    if p.suffix in ('.py','.c','.h','.md') and p.exists() and q.exists() and sha(q)==h:
        if p.read_text(encoding='utf-8-sig').splitlines()==q.read_text(encoding='utf-8-sig').splitlines():shutil.copy2(q,p)
firmware={}
for target in ['BMS_EX_Release','BMS_EX_Debug']:
    dest=out/'firmware'/target;dest.mkdir(parents=True,exist_ok=True)
    for ext in ['hex','bin','axf','map']:
        p=root/'BMS_EXv1.1/BMS_EX/MDK-ARM/Appli'/target/(target+'.'+ext)
        if p.exists():shutil.copy2(p,dest/p.name)
    firmware[target]=dict(path=str((dest/(target+'.hex')).relative_to(root)),sha256=sha(dest/(target+'.hex')))
conditions=dict(status='draft',live_ready=False,firmware_sha256=firmware['BMS_EX_Release']['sha256'],
    physical_valid=0,battery_disconnect_confirmed=True,battery_disconnect='User can remove cells on site if response does not recover',
    cells=3,load_nominal_ohm=33,charge_port='open',sample_period_ms=20,sample_stale_ms=40,
    baseline_samples=50,baseline_peak_to_peak_max_codes=100,baseline_tolerance='max(20,3*peak_to_peak)',
    command_deadline_ms=99,command_high_acceptance_max_ms=100,post_observation_ms=1000,
    cell_enter_exit_low_code=None,cell_enter_exit_high_code=None,
    blocked_by=['External flash erase failed twice; new firmware has no board identity/readback confirmation',
                'Dedicated capture latency and window coverage require disabled board rehearsal',
                'Run-specific cell entry/exit bounds are not frozen'])
(out/'conditions-draft.json').write_text(json.dumps(conditions,ensure_ascii=False,indent=2),encoding='utf-8')
work='''# G01/G02补测与G03单次继电器实现（r1）

日期：2026-11-01。软件实现与离线验证完成；新固件板测及首次真实脉冲尚未完成。当前下载阻塞在外部Flash擦除，不能将构建或寄存器模拟当成实物通过。

## 实现和已验证结果

- 独立单次状态机、TIM2本地截止、AFE四通道专用采集、辅助MCU记录、256组缓存、CRC/请求编号/防重放、共享STOP与资源互斥已实现。默认真实继电器门为0；PWM及PB5持续禁能。
- Release：0错误0警告。Debug：0错误，1条原有EXTRAM链接警告。固件哈希见artifact-manifest.json。
- g01-checks-03、g02-checks-01、g03-checks-01、adc-checks-02通过。relay-checks-04包含生产核心/适配层/协议、禁能和显式模拟的live寄存器夹具、SPI阻塞/过期/STOP/PEC/锁存/时间回绕/互斥/防重放及512字节栈帧检查。
- 主机解析与判读4项测试通过；独立复核有效AFE帧的PEC和原码。跨越撤销时刻的采样不冒充窗口内完整观测；数据不足、无明显响应及异常分别判读。真实恢复未确认时先提示断开供能，再导出缓存。
- COM11旧r4补采10秒：179条已解析原码均有效，19个完整九通道组；无内部缺序或重复。末组缺afe_vref2，54字节末尾截断保存为partial_tail，未当作有效样本。

## 下载阻塞与当前设备身份

两次STM32CubeProgrammer连接均识别ST-LINK 16004A002933353739303541和STM32N6 Device ID 0x486，在0x70100400对应外部Flash扇区擦除阶段报`failed to erase memory`，退出1；没有通过写入/读回校验。日志和各次待写HEX在flash-*目录，不覆盖。

下载前最后确认的板上运行身份为g03-adc-r4；下载失败后的启动状态尚未重新确认。已按工程原有下载流程请求用户设置BOOT1=1、BOOT0=0并RESET。成功校验后需要恢复正常BOOT并确认新身份。没有发出真实继电器或PWM命令。

## 续接步骤

1. 用户完成下载模式后，对最新候选HEX执行一次写入与读回验证，保留新attempt；验证失败不继续板测。
2. 恢复正常BOOT，确认g03-relay-r1；执行新固件禁能采集演练、G02受影响板测和G01恢复采集。真实GPIO入口仍关闭。
3. 根据禁能记录核定采集覆盖、软件截止及基线规则，冻结本次电芯进入/退出依据和工况表。conditions-draft.json目前live_ready=false，不能用于真实动作。
4. 条件满足后生成单独可追溯的真实单次构建，先完成该镜像禁能演练，再使用relay_capture.py的显式live请求执行一次；不自动循环、重试或启动PWM。

本轮补测范围与尚缺项目见retest-matrix.md；协议和计时边界见instructions/specs/G03-relay-single.md。G01/G02正式硬件验收和G03完整开环仍未判定。
'''
(out/'work-card.md').write_text(work,encoding='utf-8')
status=root/'instructions/STATUS.md';s=status.read_text(encoding='utf-8-sig')
s=s.replace('日期：2026-10-31。','日期：2026-11-01。',1)
s+='''

## 2026-11-01 最新进展：单次继电器实现，下载待恢复

g03-relay-r1已完成独立单次入口、TIM2本地截止、AFE专用采集/缓存及主机记录工具。G01/G02、合成G03、真实ADC受影响离线回归和新增继电器用例通过；Release0错0警告，Debug保留原有EXTRAM警告1条。实际输出门保持关闭。

COM11已采到旧g03-adc-r4有效原码179条（19完整组，末尾截断保留）。新固件两次下载都在外部Flash擦除阶段失败，尚未写入/读回验证；下载失败后的实际启动状态待确认。新采集的禁能板测、工况冻结及首次100ms真实脉冲未执行。G01/G02/G03正式验收状态仍为in_progress、verdict=null。

下一步：按既有下载流程恢复BOOT下载模式，完成写入与读回校验后，继续新固件禁能演练。见[本轮工作卡](../evidence/runs/20261101-G03-relay-r1/work-card.md)、[补测矩阵](../evidence/runs/20261101-G03-relay-r1/retest-matrix.md)和[单次接口规范](specs/G03-relay-single.md)。
'''
status.write_text(s,encoding='utf-8')
runlog=root/'instructions/RUNLOG.md'
with runlog.open('a',encoding='utf-8') as f:f.write('''

## 2026-11-01 G01/G02补测与G03单次继电器r1

用户授权完成无需硬件配合的补测后推进首次100ms探索，确认原接线和现场断开电池能力。实现与相关离线验证通过；旧r4在COM11补采179条有效原码，保留截断。Release0错0警告，Debug原有警告1。两次外部Flash擦除失败，未取得新镜像烧录/读回和启动证据；新镜像真实动作门保持0。已请求按现有下载流程切换BOOT。实物脉冲未执行，阶段正式判定未变。证据：evidence/runs/20261101-G03-relay-r1/。
''')
nav=root/'instructions/README.md'
with nav.open('a',encoding='utf-8') as f:f.write('\n\n- 2026-11-01实现入口：[G03单次继电器接口](specs/G03-relay-single.md)，实际进展以STATUS和本轮工作卡为准。\n')
hp=root/'instructions/specs/hardware-profile.json';h=json.loads(hp.read_text(encoding='utf-8-sig'))
h['verified_identity']['uart_last_port']='COM11'
h['g03_relay_preparation']=dict(date='2026-11-01',firmware='g03-relay-r1',live_gate=False,
    wiring_reconfirmed_by_user=True,battery_disconnect_available_per_user=True,
    new_firmware_flashed_verified=False,physical_pulse_executed=False,
    evidence_run_id='20261101-G03-relay-r1',physical_limits_unchanged=True)
hp.write_text(json.dumps(h,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
manifest=dict(run_id=out.name,mode='implementation-and-disabled-preparation',status='blocked',verdict=None,
    evidence_scope=['static','build','simulation','bench'],bench_scope='old-r4 passive G01 capture only',
    firmware=firmware,new_firmware_flashed_verified=False,physical_pulse_executed=False,source_dirty=True,
    result='Software ready; external Flash erase failed, awaiting download-mode recovery')
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'result.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ['integrate_relay.py','build-relay.ps1','flash-disabled.py','prepare-delivery.py']:
    d=out/'procedure';d.mkdir(exist_ok=True);shutil.copy2(root/name,d/name)
(out/'artifact-manifest.json').write_text(json.dumps(dict(firmware=firmware),indent=2))
print(json.dumps(firmware,indent=2))
