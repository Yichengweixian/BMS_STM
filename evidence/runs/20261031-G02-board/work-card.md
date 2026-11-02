---
unit_id: G02-board-20261031
mode: exploratory
status: in_progress
verdict: null
evidence_scope: [bench, release_boot]
---
# G02烧录及启动检查

用户明确授权烧录并推进下一步。核对最终Release及加载器SHA256、源码清单后，以既有ST-Link序列号、SWD100kHz、Under Reset写入应用地址0x70100400，不改启动加载器。

STM32CubeProgrammer退出0，Download verified successfully；实际镜像SHA256：`fd1d2a84a43fefde8e265cc879757e15c06babe2efd019f9fcf76bdb8ed4013f`。命令和原始输出见本目录flash JSON及raw日志。记录脚本在结果已保存后打印进度字符遇GBK编码错误，不影响下载/读回；未为此重复烧录。

COM9尚未观察到新固件身份，0条记录/0完整组；启动确认待用户反馈。

60秒串口只接收窗口保存在capture-01，逐通道统计见capture-01-analysis.json；没有发送控制命令。两target引脚输出门仍关闭，无自动PWM/继电器启动。本次没有执行G02同步计数窗口、波形/死区/STOP期限验证，正式判定null，G03不放行。

下一步：恢复此前正常启动的BOOT位置并RESET，确认BMS_EX及新固件日志。确认当前三路模拟源/充电/负载状态、示波器测点/探头后，制定无功率波形测试。若调试口在正常启动下不可访问，内部采样诊断需要专门的禁能测试入口，不能把普通采集日志当成100kHz时序证据。


## 正常启动确认及第二次采集

用户确认正常BOOT复位显示BMS_EX；COM9重采60秒确认fw=g02-sw-r1，1071条/119完整组，解析错误0；全部已记录raw有效=True。记录在capture-02及capture-02-analysis.json。此前capture-01零字节保留。此为复位启动，不是3次完全断电冷启动。

用户指出普通三路直流源不能接受充电回灌。明确三路源仅沿用G01电压模拟背景，不安排用其接受15V充电输入；G02当前为无功率逻辑/时序阶段。尚未确认当前源输出及负载接线，未开启PWM/继电器。测点电气定义为PA9与PF7对板GND；旧照片GND环可辨，具体PWM引出点待局部照片/接线核对。
