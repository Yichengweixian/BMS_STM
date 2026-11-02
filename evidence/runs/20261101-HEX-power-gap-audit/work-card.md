# 20261101-HEX-power-gap-audit

日期：2026-11-01。任务：通过老师HEX寻找快速电流/过流、驱动时序、单次PWM执行与工况的解决办法。

## 范围与方法

源HEX哈希为 `dd44fae11ed542ad6bcee45b35a13e93bd6632481b7d29662afda8ac7856be7f`，独立于当前源码构建产物。读取最新G03状态和三次继电器/禁能ADC证据，重新校验HEX记录，以GNU objdump的ARMv8.1-M/Thumb解码跟踪ADC、AWD、TIM1和业务状态机。对照实际HAL寄存器访问、18个编译期常量断言与ST RM0486 Rev4。

对单次PWM部分新增与现有工程隔离的纯C候选控制核及故障注入测试；不改变当前Keil target、板级适配器和实板固件。独立代码复查发现并修复新ADC样本可能掩盖既有断采超时的问题，保留回归用例。

## 验证与结论

- 6511条HEX记录校验通过，104056字节载荷，8组指定地址字节检查通过。
- 18个STM32N647 HAL/CMSIS编码断言以Cortex-M55目标编译检查通过。
- 候选控制核的实际测试输出、编译参数与案例见candidate目录；模拟输出不能证明电气关断。
- 指令地址、语义恢复、已知事实与物理未知分开记录于review.md及分项报告。

逆向分析和离线候选交付完成；三项实物问题仍未整体闭合。硬件阶段verdict保持null，不修改hardware-profile的未知值，不追加硬件通过或实际PWM运行记录。

## 产物与限制

主报告review.md、adc-analysis.md、pwm-analysis.md、verification-notes.md，带机器码的四份汇编摘录、inventory/byte-checks/manifest/result，以及candidate源码/测试/接入说明。完整二进制、全文汇编和工具/手册留本机分析区。

未访问串口、烧录器或仪器；未修改现有产品源码；未执行功率动作。编译候选core不等于形成完整可烧录的真实PWM固件。当前基于已有记录的板上身份仍为g03-relay-r2，本轮没有重新确认板端状态。
