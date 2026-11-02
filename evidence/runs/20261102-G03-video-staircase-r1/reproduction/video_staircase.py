from pathlib import Path
import argparse,json,subprocess,sys,time,hashlib,shutil

ROOT=Path('D:/ADMIN/Desktop/WEIJI/zonghe')
RUN=ROOT/'evidence/runs/20261102-G03-video-staircase-r1'
IMAGE=ROOT/'evidence/runs/20261102-G03-discharge-d74-c1/firmware/BMS_PWM_Power_Release/BMS_PWM_Power_Release.hex'
SHA='001577eeccc6ab3d264283cb4d85be17e19051a08dccc2eb983f02fd9da2d4ab'
POINTS={'D90':(0x50393303,1800),'D80':(0x50393304,1600),'D74':(0x50393402,1480)}
p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','query','start']);p.add_argument('--point',choices=list(POINTS));p.add_argument('--operator-ready',action='store_true');a=p.parse_args()
if a.action=='prepare':
    RUN.mkdir(exist_ok=False)
    protocol={'firmware':'g03-power-d74-c1','image_sha256':SHA,'points':POINTS,'ARR':2000,'window_us':2000000,
        'minimum_off_gap_s':30,'gap_basis':'recording/handling interval; not a claimed thermal reset time',
        'no_continuous_D_step':True,'video_suggested_pre_s':3,'video_suggested_post_s':5,
        'preferred_reading_window_s_after_pwm_start':[.5,1.5],
        'reading_rule':'use visibly refreshed stable plateau; do not assume settling from elapsed time; unobserved values stay null',
        'source_settings':{'each_V':3.5,'CC_A':.6,'OCP_A':.55,'OVP_V':3.65},
        'reference_scope':'PSU current display crosscheck and DMM voltage via user video; not final G01 same-shunt calibrated reference',
        'automatic_retry':False,'calibration_coefficients_changed':False,'thermal_steady_state_claim':False}
    (RUN/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
    (RUN/'work-card.md').write_text('''# 录像参考的固定D阶梯记录

目的：按D0.90、0.80、0.74各自独立记录，补D0.90电源电流参考，并检查已有两点的重复性；用于G03曲线与G01标定前交叉测量，不声称正式电流标定。

使用现有c1和原保护，不烧录、不调阈值。每点2秒，点间PWM/继电器关闭至少30秒，且输出位/故障/资源恢复和人工观察正常后才进入下一点。30秒是拍摄/记录间隔，不是温度已恢复的判据。三路电源可保持原设置供电，最后全部OFF；异常立即全部OFF，失败不重试。

录像建议覆盖动作前至少3秒至停止后至少5秒，尽量同框看到三个源的A读数和DMM电压。优先读窗口中段约0.5～1.5秒已刷新的稳定显示；若仪表尚未稳定/未刷新或未拍到，记未取得。不能因规定了时间就推定电气或热稳态，也不为读表自动延长带载。

电源电流是各自供电支路显示，不相加；DMM仍测负载电压。录像尚由用户保管，只有收到原视频后才可登记本地文件/哈希和逐帧对应。板端CSV和用户读数分开保存。正式G01需要同分流支路独立电流参考、比较方法不确定度及独立新run验证；本轮不写新系数。

每点从输出关闭启动、固定D、结束回零，不在一次令牌中连续改CCR；这是分段阶梯，不是PI或恒流设定阶梯。当前实物状态以实际run和STATUS为准。
''',encoding='utf-8')
    repro=RUN/'reproduction';repro.mkdir()
    shutil.copy2(ROOT/'scripts/g03/power_capture.py',repro/'power_capture.py')
    shutil.copy2(__file__,repro/'video_staircase.py')
    print(RUN);sys.exit(0)
assert a.point
profile,ccr=POINTS[a.point]
assert hashlib.sha256(IMAGE.read_bytes()).hexdigest()==SHA
folder=RUN/a.point.lower()
if a.action=='start':
    assert a.operator_ready,'operator confirmation required'
    q=json.loads((folder/'before-query/result.json').read_text())['status']
    assert all(q[k]==0 for k in ('phase','faults','used','owned','bits'))
    keys=list(POINTS);index=keys.index(a.point)
    if index:
        prev=RUN/keys[index-1].lower()
        assert json.loads((prev/'live/result.json').read_text())['verdict']=='pass'
        last=json.loads((prev/'capture-ended.json').read_text())
        gap=time.monotonic()-last['monotonic_s']
        assert gap>=30,f'Off gap still pending: {30-gap:.1f}s; no start sent'
    dry=json.loads((ROOT/'evidence/runs/20261102-G03-discharge-d74-c1/new-image-dry-03/result.json').read_text())
    assert dry['verdict']=='pass'
    contract={'profile':profile,'firmware_sha256':SHA,'D':ccr/2000,'CCR':ccr,'ARR':2000,'run_us':2000000,
        'source_wiring_confirmed':True,'source_settings_confirmed':True,'source_cv_confirmed':True,'no_real_cells':True,
        'load_connected':True,'charge_port_open':True,'new_image_default_off_verified':True,'dry_run_passed':True,'source_paths_reviewed':True,
        'operator_confirmation':'user confirmed source idle/no anomaly and video ready for this point',
        'inherited_short_evidence':{'D90':'20261102-G03-discharge-sprint-r2/live-d90-01','D80':'20261102-G03-discharge-sprint-r4/live-d80-short-01','D74':'20261102-G03-discharge-d74-c1/live-d74-short-01'}[a.point],
        'physical_short_current_ceiling_confirmed':False,'minimum_off_gap_s':30,'no_automatic_retry':True}
    path=folder/'contract.json';assert not path.exists();path.write_text(json.dumps(contract,indent=2),encoding='utf-8')
    mode='live';out=folder/'live'
else:mode='query';out=folder/'before-query'
cmd=[sys.executable,str(ROOT/'scripts/g03/power_capture.py'),'--port','COM12','--mode',mode,'--profile',hex(profile),'--out',str(out),'--image',str(IMAGE),'--sha256',SHA]
if mode=='live':cmd+=['--contract',str(folder/'contract.json')]
r=subprocess.run(cmd,timeout=45)
if mode=='live':
    (folder/'capture-ended.json').write_text(json.dumps({'monotonic_s':time.monotonic(),'unix_s':time.time(),'exit_code':r.returncode,'automatic_retry':False}),encoding='utf-8')
sys.exit(r.returncode)
