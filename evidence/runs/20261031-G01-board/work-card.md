---
unit_id: G01-board-20261031
title: Release实板烧录及9通道连续原码验证
requirement_ids: [G01.1, G01.2, G01.3]
mode: exploratory
status: complete
verdict: null
evidence_scope: [static, build, simulation, bench, release_boot]
run_ids: [20261031-G01-board]
---

# 实板采集工作卡

用户授权烧录新的Release并采实际串口，必要时由用户切换BOOT。实物标定按用户要求继续推迟；不启动PWM或充放电控制。

## 实际操作与发现

1. 连接检查：ST-Link存在，正常BOOT下无法读core；CH340初始未连接。用户切到开发模式并接回串口后识别COM9，VID1A86/PID7523。
2. 将已归档r1镜像写0x70100400并读回校验成功。用户恢复正常BOOT、RESET，屏幕BMS_EX；capture-01取得756条记录，MCU ADC有效，8路AFE因CONFIG错误无原码。失败记录和镜像未覆盖。
3. 查ADBMS1818数据手册Table72，发现GPIO写是下拉控制、读是实际输入电平，不能逐位回读比较；DTEN/MUTE亦为只读状态。修正掩码，但REFON/ADCOPT/DCC/冗余等可回读字段仍严格检查。扩展真实语义回归，新增4类真实配置不符拒绝测试。r2原生C故障测试、7项Python解析测试及36条回放通过。
4. r2 Release干净构建0错误0警告；Debug0错误、原有.EXTRAM警告1个。第二次烧录及读回校验成功（flash-02.log）。用户恢复正常BOOT并RESET，再次显示BMS_EX。
5. capture-02接收真实COM9数据，串口元信息确认fw=g01-sw-r2，镜像SHA256 `dfe902bbf676e214cdf41f4a3a7bab6f1217e6b6506359a93a3a99bfe7d39dd5`。没有发控制命令。

## 观察结果

实际采样首尾跨度 **71.603秒**，**144完整组、1296条**，全部9通道raw_valid=1；所有status=128，仅标记未标定。串口解析错误0，记录中未见PEC、超时、序号丢失/重复或异常复位。捕获边界缺组情况按analysis原样记录；不以清洗后的数据替代原始数据。

| 通道 | 记录数 | 原码有效数 | 原码范围 | 周期间隔中位数ms |
|---|---:|---:|---|---:|
| cell1 | 144 | 144 | 38909—38913 | 501 |
| cell7 | 144 | 144 | 38914—38918 | 501 |
| cell13 | 144 | 144 | 38925—38929 | 501 |
| current_afe_gpio1 | 144 | 144 | 8993—9004 | 501 |
| temperature_gpio2 | 144 | 144 | 3218—3223 | 501 |
| temperature_gpio3 | 144 | 144 | 3223—3228 | 501 |
| temperature_gpio4 | 144 | 144 | 3218—3221 | 501 |
| current_mcu_adc1 | 144 | 144 | 639—1041 | 501 |
| afe_vref2 | 144 | 144 | 30015—30018 | 501 |

这次是正常BOOT复位启动，不是重新完成3次完全断电冷启动。UART流连续与原码有效不代表两路电流已经标定、方向正确或温度模型已确认。所有正式物理值/参考值留空；未改硬件未知限值。

## 证据与后续

- 原始字节/事件：`capture-02/raw/`；解析CSV：`capture-02/derived/device.csv`；SHA256：`capture-02/manifest.json`。
- 全通道统计及失败轮对照：`capture-02-analysis.json`、`capture-01-analysis.json`、`result.json`。
- 固件与MAP：`firmware-r2/`；构建日志：`BMS_EX_Release-r2.log`、`BMS_EX_Debug-r2.log`；回归：`checks-r2/`；修改前源码：`before-r2/`；最终身份：`source-r2-manifest.json/source-r2-snapshot.zip`。
- 当前BOOT保持正常启动，实物标定与独立验证仍待参考仪表、电流通路/极性、温度传感器/参考温度确认。正式G01 verdict=null。
