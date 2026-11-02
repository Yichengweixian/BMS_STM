---
unit_id: prepower-host-20261031
title: 开环前上位机实现与扩展验证
requirement_ids: [G02.2, G02.3, G02.5-software, G03.1-preparation, G03.3, G05.1, G05.2, G05.3, G05.4-disabled, G05.5-bounded]
mode: exploratory
status: complete
verdict: null
evidence_scope: [static, build, simulation, bench, release_boot]
run_ids: [20261031-prepower-host]
---

# 开环前上位机工作卡

本轮范围为当前无需探头、硬件标定或带功率接线的实现与验证。用户明确跳过上述硬件帮助，仍配合了BOOT切换。未开启引脚功率输出或继电器，未执行开环充放电。阶段进度统一见STATUS；本卡complete仅表示本轮范围完成。

## 实现与身份

修复r1被拒COMPARE污染下一次START参数；g02_link在非OK后恢复参数。test_link先复现失败并保留rejected-command-before，再由checks-fixed/checks-final验证修复。新镜像g02-host-r2，Release HEX SHA256 `2a75563eff600af7049202a29d77649a3ebea0edba06ddeca8793899d93a4012`，下载地址0x70100400；没有修改FSBL或OTP，两个target引脚输出门关闭。

新增extended_diagnostics.py自动执行13组板测、原始收发和CSV记录；仅接受r2及关闭的输出gate。解析器仍可回放旧r1，严格检查无符号十进制、CRC和请求范围。复位、坏响应及超时不自动重启，识别固件后异常尝试STOP。

prepower_plan.py为纯离线工具：实际profile提供允许范围/持续时间，未知即拒绝；固定工况量化后再检查范围，STOP/故障终止剩余点。port_power只处理有标定身份、单位/端口/会话/参考方向、有效且时间对齐的数值。模板未知项保留null。offline-example.json是显式合成软件夹具，不是实物参数或转换器仿真。此工具不存在串口功率执行路径。

## 结果与证据

| 检查 | 结果 | 位置 |
|---|---|---|
| 生产C状态机/端口/串口 | 严格编译通过；默认/模拟引脚gate分支、故障与协议回归通过 | checks-final/ |
| Python主机/工况 | 14项通过：CRC、帧、复位/超时不重放、错误固件/gate、请求耗尽、顺序/量化/停止/故障、未知限值及功率有效性 | checks-final/host-python.stderr |
| G01回归 | 生产C、16项Python、36条合成回放通过 | g01-regression-fixed/ |
| ARM构建 | Release 0错0警告；Debug 0错1条已有EXTRAM警告 | raw/BMS_EX_*.log、build-results.json |
| 烧录及正常复位 | 下载/读回校验成功；用户BOOT00复位后实际r2协议和测量元数据匹配 | flash-result-01.json、raw/flash-01.log、board-01/ |
| 实板扩展 | 13组全部通过；CRC、NaN/Inf、超长/溢出数值、重复/冲突/过期、分片粘包、被拒参数无副作用、BUSY不替换窗口、CCR边界、STOP与故障 | board-01/result.json、events.jsonl、serial.bin、reports.csv |
| 主机关闭及压力 | 关闭串口句柄未发STOP，本地1000ms窗口自动收尾，重连只查询；20条无效业务命令有界压力期间无ADC错误 | board-01/ |
| 重复10秒窗口 | 3次每次更新/ADC各999998，合计2999994；OVR/ADC错误/late_irqs为0 | timing-summary.json |
| G01恢复及连续记录 | 60秒1071条/119完整九通道组，全已解析raw有效；无解析错误/缺序/重复 | g01-resume-60s/、g01-resume-summary.json |
| 真实profile预检 | 26项限值/证据要求未满足，未知duty/duration拒绝编译，power_execution_available=false | preflight-final/result.json |

本次9个bad_frames是主动注入的非法帧，不隐藏为零；接收错误计数为0。未做物理USB拔线。10秒采样数是ISR服务次数，UIF可合并，999998对名义1000000的差异不被事后指定为通过容差。统计不能证明物理频率、无漏触发、采样相位或驱动停止时间。

## 已保存失败与工具修复

rejected-command-before为修复前真实回归失败。g01-regression中测试和回放已成功，但最终报告因Python3.8相对__file__路径失败；脚本改用resolve()后在新目录重跑通过，旧结果保留。此错误不属于板端采样异常。

## 跳过项与允许结论

无需硬件协助的本轮实现、回归、禁能台架与记录链检查完成；新镜像正常复位启动已证实，未重新做冷启动3次。波形/驱动死区/实际停止、标定、实物隔离、功率失联及过流期限均跳过并保持null。局部D→I方向及真实功率曲线不存在，不用合成数据补齐。不放行受限带载，且不要求用户提供其已说明无法完成的探头操作。

详细操作与边界见../../../instructions/specs/prepower-host-validation.md。源快照、工具版本和改动前后哈希一并归档；本卡不声称完整G05功率业务验收或G03实物通过。
