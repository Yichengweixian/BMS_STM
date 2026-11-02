---
unit_id: G03-real-cells-baseline-20261031
mode: exploratory
status: complete
verdict: null
evidence_scope: [bench, static]
---

# 三电池与33Ω负载接线下的禁能基线

用户确认现在装三节真实电池，放电端接此前33Ω负载，充电端开路无电源，并要求继续测试。已更新实物profile，不再沿用此前三路直流源接电池座的会话状态。用户报告不等于继电器触点、热能力或驱动状态已经实测。

本轮实际执行20秒COM9只读采集，以及一次G03 STATUS查询；未发送START、合继电器或使能PWM命令，没有进行真实放电。固件仍为g03-disabled-r1，其G03保护输入仍为合成夹具。当前真实测量链未形成可用的物理电流保护闭环，不能直接打开现有禁能版来试放电。

结果：360条/40完整九通道组，全已解析raw有效，无解析错误、缺序、重复。cell1/cell7/cell13按AFE标称比例的均值分别约3.8907/3.8907/3.8911V；选定三通道之和约11.6725V。这里只是未独立校准的通道换算，不作电池健康或运行范围判定。AFE电流通道raw8994—9002，MCU电流通道raw1006—1012；未知增益/极性及实际同支路关系，不换算为已验证安培，也不把静态原码当确定零电流。

状态查询确认STOPPED、faults=0、configured=0、shadow_pwm/relays=0、actual_bits=0、power_capable=0。它支持软件/寄存器禁能观察，不证明触点或栅极的物理关断性能。

尚未执行的用户目标：真实开环放电。所需缺项仍是可信的电流方向/换算及阈值、真实测量接入MCU保护、适用电池/转换器限值与驱动/停止依据。负载已连接与用户启动授权均已确认，不再以“没有授权”或反复询问接线解释未启动。此处阻塞属于实际保护和硬件证据尚未具备，不用合成保护参数代替。

原始数据在capture/raw，解析结果在capture/derived，完整统计summary.json，名义换算baseline-values.json，唯一查询在status-query。status=complete只指本次禁能基线，不代表放电实验完成。
