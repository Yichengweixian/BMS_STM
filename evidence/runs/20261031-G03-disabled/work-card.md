---
unit_id: G03-disabled-20261031
title: G03 禁能状态机与 MCU 本地保护
requirement_ids: [G03.1-preparation, G03.2-disabled, G03.3, G05.1, G05.2, G05.4-disabled]
mode: exploratory
status: complete
verdict: null
evidence_scope: [static, build, simulation, bench, release_boot]
run_ids: [20261031-G03-disabled]
---

# G03 禁能实现工作卡

本轮按用户要求完成禁能充放电状态机、MCU本地保护和现有资料核对。探头与物理标定跳过；没有启动真实充放电。源码及板端镜像为g03-disabled-r1，Release HEX SHA256为`d94e10e2f5cc144a495125e9461abb4d570af8afcf9daf6567aa4b732ce763a6`，入口0x70100400。FSBL/OTP未改；默认无G03自启动、两个target的G02引脚门仍关闭。

## 实现与边界

- `g03_control.c/h`：STOPPED/BREAK_WAIT/RELAY_WAIT/CHARGE/DISCHARGE/DECAY_WAIT/FAULT。固定手动CCR，运行中换向BUSY，无队列重启；STOP先撤销影子PWM、等待最小衰减且电流满足释放条件，再撤销影子继电器；衰减超时锁存。CLEAR不启动、重复初始化不清锁存。
- `g03_port.c/h`：短临界区隔离主循环命令与SysTick，本地tick检查心跳期限、运行时限、有效性/标定标志、过期、各节欠压/过压、正负电流、反流、温度、互锁及外部故障。只调用既有寄存器禁能，没有使能真实PWM/继电器接口。G02采样和G03互斥，旧STOP也执行G03停止。
- 夹具数值在g03_port.c中明确标为合成软件测试，未填入实物limits。G03输入不来自未标定G01；G03校准标志为合成输入字段，不能视作传感器已标定。响应强制synthetic=1、power_capable=0，并报告影子动作与实际位图。
- 协议扩展op10—19，沿用CRC/全局递增id，重复请求不重复执行，重复heartbeat不续期，STATUS不续期。上位机保存原始收发、CSV、哈希；失败尝试STOP，不自动清故障重启。

完整接口、字段、测试夹具和操作见[禁能软件契约](../../../instructions/specs/G03-disabled.md)。

## 验证记录

| 检查 | 结果 | 证据 |
|---|---|---|
| 生产核心 | 两方向、顺序、边界、数据质量、符号、温度、时钟回绕、失联、衰减、重复Init和10000事件序列不变量通过 | checks-final-03/core.stdout |
| 生产寄存器适配/串口 | 合成十种故障、每tick输出寄存器禁能、G02互斥、共同STOP、重复heartbeat不续期、C帧/Python解析交叉检查通过 | checks-final-03/ |
| 新主机异常测试 | 5项通过：CRC/数值/分片、错误实际输出或能力、复位、超时/序号耗尽不重放 | checks-final-03/host-python.stderr |
| G01/G02回归 | 生产C与既有Python、36条G01合成记录、G02协议/端口通过 | g01-regression/、g02-regression-final/ |
| 构建 | Release 0错0警告；Debug 0错1条已有EXTRAM警告 | build-results-final.json、raw/*-final.log |
| 烧录/启动 | Flash读回成功，用户BOOT00复位后协议/采集元数据匹配；未重复冷启动 | flash-result-01.json、raw/flash-01.log、board-01/ |
| G03实板 | 8组检查、143份状态报告；十种合成故障及锁存、重复心跳不续期、关闭主机句柄后本地失联等通过 | board-01/result.json、serial.bin、events.jsonl、reports.csv |
| 实际输出观察 | 所有状态报告actual_bits=0；最终STOPPED/faults0/configured0，影子PWM/继电器0 | board-summary.json |
| G02实板回归 | 1秒/10秒内部采样、CCR/STOP/故障/CLEAR通过；10秒更新/ADC各999998，OVR/ADC错误0 | g02-board-regression/ |
| G01恢复 | 30秒531条/59完整组，全raw有效，解析错误/缺序/重复0 | g01-resume-30s/、g01-resume-summary.json |

本地失联使用夹具800ms期限，具体stop_ms-heartbeat_ms差值保存在board-summary.json；已观察活动tick最大间隔1ms。这不包含真实驱动传播或触点动作，不是独立硬件看门狗；CPU停止/全局屏蔽中断时不保证SysTick服务。RELAY_WAIT短阶段在原生测试已验证，串口采样没有覆盖所有中间状态，不把未拍到的状态伪称实板逐态观测。

## 资料与失败保留

[资料核对](document-review.md)直接重读5份课程/手册，来源哈希document-sources.json、66段摘录document-excerpts.json。保留继电器停止示例冲突、INA199A2/50倍冲突、实际驱动死区与GPIO映射待验证；未找到匹配N647底板的独立原理图或出厂测试记录，F4图不套用。

checks-final/build-link.stderr保存首次嵌套测试main宏冲突；修改测试入口后checks-final-02/03通过。原始尝试未覆盖，板测无自动重试或重新定义通过阈值。源码快照/清单、改动前文件、diff和交付哈希归档在本run。

## 未执行事项

实际电芯/电流/温度标定、Vgs/死区、继电器真实隔离与释放条件、硬件停止时限和D→I方向均未验证。没有给真实功率模式填默认阈值或提供解锁接口。真实越流保护的有效性还需要已标定输入、确认阈值与关断执行路径；本次通过只覆盖合成输入下的保护算法和板端执行。阶段状态仍in_progress、正式verdict=null；本卡complete只表示所授权禁能工作完成。
