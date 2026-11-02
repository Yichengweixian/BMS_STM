---
unit_id: G01-software-20261031
title: G01 原码采集与无效数据处理
requirement_ids: [G01.1, G01.2, G01.3]
mode: exploratory
status: complete
verdict: null
evidence_scope: [static, build, simulation]
freeze_status: exploratory_snapshot
target: [BMS_EX_Release, BMS_EX_Debug]
run_ids: [20261031-G01-software]
---

# G01 软件工作卡

## 范围与条件

用户要求完成 G01 能独立推进的软件部分：连续原始数据、启动ADC采样、修复无效值；实物标定等万用表到手再做。沿用 G00 的板型、编译工具与外设线索，不把旧固件启动证据当作新固件证据。实际传感器/电流增益/极性/电源/参考仪表未知，均未填假值。

## 实现

1. G01.1：9个通道字典、两条电流独立命名、12bit/过采样比例和100uV码值缩放。详见 [协议与使用说明](../../../instructions/specs/G01-software.md)。
2. G01.2：ADC1改软件触发，每500ms独立采样，HAL状态/10ms轮询超时/码值边界处理；AFE用新有界驱动，配置读回PEC、清转换寄存器、PLADC完成查询与20ms超时；失败时不读旧转换值，不将PEC错误补成0。没有启动PWM/继电器功率控制；ADC2留待所需电压通道工作。
3. G01.3：带seq/转换窗口/龄期/原码/状态/原帧/校验的ASCII CSV；estimated与physical分离，全部未标定、physical_valid=0。RX不再原样回显，避免污染记录流。提供只读串口记录器、离线回放和同生产C源码的HAL故障注入。

## 实际验证

- 最终干净重编译：`BMS_EX_Release-final.log` 0错误0警告、退出0；`BMS_EX_Debug-final.log` 0错误1警告、退出1，仍是G00已有`.EXTRAM` L6314W，未引入新警告。
- `checks-03/checks.json` 保存实际命令与退出码；GCC以 `-Wall -Wextra -Werror` 编译生产测量C及模拟HAL。AFE忙至少5ms后完成、SPI超时/读失败、配置不符、坏PEC、转换未更新、ADC启动/等待/错误/停止失败/边界、独立调度、过期/回绕、所有小缓冲截断均有断言。
- 7项Python测试通过：合法/无效记录、串口校验、截断、单位/状态/原码/派生字段不一致、AFE坏PEC保留、丢帧/重复/复位/回绕。
- 生产C生成的36行模拟串口数据，经记录器解析得到9通道，0解析错误，physical/reference始终空，未覆盖原始字节。证据在 `checks-03/replay/`，明确simulation。
- `release-hex-check.json` 独立检查HEX记录校验和及应用地址；镜像、MAP及SHA256在 `firmware/`、`build-results.json`。本次没有烧录，没有板端G01日志。
- `before/` 保存实际修改前的文件，`source-manifest.json/source-snapshot.zip` 固定交付源码/配置；Git原有修改保留，`working-tree.diff`包含整个未提交工作树，不能将其全部归属本任务。
- 首轮本机测试对MinGW snprintf截断返回值预期不兼容，失败保留在checks-01；兼容负返回值后，进一步补全尾部校验截断处理并穷举缓冲边界。checks-02为中间通过记录，checks-03为最终源码检查。

## 判定与未完成

本卡的软件实现/构建/离线检查完成，正式G01判定仍null。没有独立仪表、已确认电流通路/方向或探头型号，不能出具电流/温度标定或准确性结果；ADC1尚未在新固件上取得实板启动和原码验证。PT1000估算及1.8V名义参考只作诊断。ADC2、实际模拟前端限幅和开短路检测未被本次码值检查覆盖。

下一步：将新Release镜像下载到板上，恢复已验证的正常启动BOOT位置，按说明录制60秒G01数据，确认9通道原码/质量状态；若缺烧录模式切换，由用户按既有BOOT步骤操作。随后在参考仪器和接线明确后另开G01.4标定run。温度完整标定还需要参考温度计及探头类型，单有普通万用表不能替代。
