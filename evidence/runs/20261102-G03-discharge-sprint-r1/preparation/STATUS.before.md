# 当前状态

日期：2026-11-01。本表为正式阶段验收状态；同工况三次继电器探索及单次PWM禁能接入/板测已完成，真实PWM工况仍单独推进。

|阶段|status|verdict|已有证据 / 剩余工作|
|---|---|---|---|
|G00 基线与硬件契约|in_progress|null|构建/烧录及历史冷启动基础项完成，三节14500、33Ω负载、充电口开路已登记；物理额定值、散热和仪器校准缺项保留|
|G01 测量与标定|in_progress|null|本轮有效性/完成/错误传播/时间戳/序号/复算与快速AFE时序补测完成；真实动作后264条有效原码、29完整组；物理V/I/T标定和MCU电流路径问题仍未闭合；追加448点禁能输入交叉检查及新PWM版本270条/30组常规采集恢复验证|
|G02 无功率PWM与时序|in_progress|null|受影响软件回归、13组禁能板测、STOP/锁存/协议异常/资源互斥完成；新增单次PWM禁能15项及采集恢复通过；物理波形、有效死区与电气停止时间缺测|
|G03 受限开环功率级|in_progress|null|三次独立PG5同工况观察均响应并恢复，命令98.528565—98.530300ms，每次4组完整窗口样本，最终输出0/故障0；单次PWM禁能接入/双构建/读回/15项板测已完成，实际PWM工况的路径与驱动/停止依据仍待落实|
|G04 PI恒流与故障退出|not_started|null|尚无闭环实物证据|
|G05 串口/上位机联调|in_progress|null|CRC/id/防重放、专用采集读回、停止与单次命令工具完成；真实恢复未确认先提示现场停止；完整功率业务仍未验收|
|G06 SOC基准与数据集|not_started|null|容量、初值、参考标签及独立验证尚待建立|
|G07 模型与端侧部署|not_started|null|无可验收数据集或模型产物|

当前实板正常运行 `g03-pwm-disabled-r1`，Release HEX SHA256为`9126778404c6f9a9890ab729522f7fbd9fe7fe0a380436694494ebecde81f9fb`。ROM下载写入/读回成功，用户恢复BOOT1=0/BOOT0=0并RESET后COM11核对默认禁能及身份。单次PWM禁能15项全部取得通过结果，G01恢复270条/30完整组，G02 1秒更新/完成99997无错误，relay DRY102组。最终PWM IDLE、used1、faults0、owned0、timer_running0、actual_bits0；物理量有效标志保持0。本版不能开启真实PWM或继电器。

核心21组、port寄存器模型15组、主机19项及受影响旧回归通过；Release0错0警告、Debug原有EXTRAM警告1。一次软件复位接口Error32保留，独立串口证实默认启动后继续未执行场景，无复位/启动自动重试。详见[禁能工作卡](../evidence/runs/20261101-G03-pwm-disabled-r1/work-card.md)、[最终报告](../evidence/runs/20261101-G03-pwm-disabled-r1/report.md)。未新增断电冷启动或电气关断结论。

历史真实继电器镜像 `g03-relay-r2` / `8ff78e03997c4a5facd8f6feade09024fdd4721a3f0e32fc3531312bf1598c49` 与三次观察数据保留。此版下载后不再把旧固件的live_used状态当作当前运行状态。

此前完成r1禁能实测及G01/G02补测，固定r2观察边界并完成首次真实命令；用户继续G03后，沿用同一条件追加两次独立记录。三路电芯与AFE均观察到相关响应，AFE恢复；软件窗口不是触点测量。未知制造商硬限和实际电流标定仍留空，观察区间仅属于本次工程探索。

此前继电器交付：[工作卡](../evidence/runs/20261101-G03-relay-r2/work-card.md)、[补测表](../evidence/runs/20261101-G03-relay-r2/retest-matrix.md)、[首次报告](../evidence/runs/20261101-G03-relay-r2/first-experiment-report.md)、[冻结工况](../evidence/runs/20261101-G03-relay-r2/conditions-table.md)。失败历史与已完成动作见RUNLOG和各run。r1恢复采集的截断位于开头；r2恢复采集为末尾9字节截断，均保留且不参与有效样本判定。

此前交付：[重复性工作卡](../evidence/runs/20261101-G03-relay-repeat-r1/work-card.md)、[三次曲线](../evidence/runs/20261101-G03-relay-repeat-r1/comparison/aligned-responses.png)、[PWM准备](../evidence/runs/20261101-G03-relay-repeat-r1/pwm-preparation.md)。AFE三次中位响应−2492.5/−2493/−2491码；MCU为+0.5/−1/0码，不能作为已验证的快速反馈。手动RESET后曾停留ROM且串口无响应，软件复位恢复；该启动问题保留，未新增冷启动通过结论。禁能适配器已接入；下一项落实本次PWM路径的反馈或快速保护、实装驱动及有限工况，随后接真实输出版本。EG3112资料支持内部死区，DTG0不单独否决，不要求完整原理图作为禁能工作的前提。


此前输入诊断：[MCU电流输入工作卡](../evidence/runs/20261101-G03-current-path-r1/work-card.md)。7组448点完成并核对原始CRC/聚合值，PA1原采样/长采样/恢复后的尾段中位数1272/1232/1271码；模拟供电有效位、模拟引脚模式和通道配置读回符合源码，寄存器与ADC状态全部恢复，第三次继电器记录保留，输出0。静态检查未定位I_ADA至PA1的实际连接或传递关系，根因仍inconclusive，真实PWM未执行；用户确认没有完整原理图，需要板厂资料或具备条件的路径确认，不以修改系数替代。
