# G03 同工况重复性与PWM单点准备

日期：2026-11-01。任务3及任务4的同工况短时记录：status=complete，verdict=pass（仅三次响应方向和恢复一致性）。任务5的参数计算/条件核对：已交付；真实PWM执行与完整G03验收仍未完成。

本次追加两次独立PG5命令，与此前首次实验合计三次。使用同一g03-relay-r2镜像、三节电池/33Ω负载/充电口开路，以及完全相同的100ms上限、采集和退出规则。每次先确认初始禁能，再独立显式触发；无自动循环、无异常重试、无PWM/PI。

|记录|请求id|PG5软件命令ms|完整窗口样本|AFE中位变化（码）|MCU中位变化（码）|恢复/故障|
|---|---|---|---|---|---|---|
|首次live-01|2520201630|98.528565|4|−2492.5|+0.5|已恢复 / 0|
|第二次repeat-02|2521445083|98.530290|4|−2493.0|−1.0|已恢复 / 0|
|第三次repeat-03|2521666429|98.530300|4|−2491.0|0.0|已恢复 / 0|

AFE变化按“完整窗口中位数−动作前50点中位数”复算，三次差幅为2码，仅描述这三次数据的离散程度，不宣称电流准确度或大样本重复性指标。每次均有102组有效采集，最后5个AFE样本回到各自冻结比较带，三路电芯同步下降并回升。MCU通道未跟随明显的AFE变化，不能作为已验证的快速电流保护输入。其基线开始处的暂态原样保留，没有删掉后冒充完整低噪声基线。

## 启动异常与当前档位

当前应保持运行档BOOT1=0、BOOT0=0。第二次记录前，用户按RESET后COM11状态请求超时，5秒被动监听也没有字节；SWD只读得到VTOR=0x18000000，CFSR/HFSR=0，未进入r2应用。没有发送真实触发。一次Hot Plug软件复位后恢复r2、IDLE、输出0及live_used=0，再执行第二次。

第二次已保存并复算恢复后，为第三次另行执行一次显式软件复位，确认IDLE后单独发送一次新请求。不是重放第二次命令，也没有自动复位/循环脚本。手动复位未进入应用的根因仍未确认，不能将软件复位恢复算作新一轮冷启动通过。所有无响应及启动寄存器记录保留。

最终查询仍为DONE=5、faults=0、actual_bits=0、live_used=1。第三次结果保持锁存，本轮未重新烧录或改变固件、阈值、脉冲长度。

## 交付与下一项

- [三次对照指标](comparison/comparison.json)、[对照CSV](comparison/comparison.csv)、[时间对齐曲线](comparison/aligned-responses.png)。
- [第二次原始结果](repeat-02/result.json)、[第三次原始结果](repeat-03/result.json)；各自含manifest、serial.bin、events.jsonl、samples.json/CSV、response.png及derived中的标称换算/停止事件/哈希。
- [冻结规则](conditions-frozen.json)、conditions-ready-02/03.json、[最终查询](final-status/result.json)。
- [PWM准备分析](pwm-preparation.md)、[机器可读缺项](pwm-readiness.json)、[软件交付与8项验证](software-delivery/manifest.json)。
- [比较工具](../../../scripts/g03/compare_relay_runs.py)、[PWM时序工具](../../../scripts/g03/pwm_point_plan.py)、[绘图工具](../../../scripts/g03/plot_relay_comparison.py)。

下一项优先定位PA1电流反馈路径或落实独立的快速过流保护，并确认驱动映射、有效死区和输入能量约束，再接真实PWM执行适配层。当前不会因继电器重复成功就把PWM门打开。任务4的更长记录也未执行，原33Ω/25W标签不作为已核验的连续散热能力。
