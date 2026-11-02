---
unit_id: G02-software-20261031
title: G02 默认禁能 PWM/ADC 诊断与停止
requirement_ids: [G02.1, G02.2, G02.3, G02.4-preparation, G02.5-software-review]
mode: exploratory
status: complete
verdict: null
evidence_scope: [static, build, simulation]
freeze_status: exploratory_snapshot
target: [BMS_EX_Release, BMS_EX_Debug]
run_ids: [20261031-G02-software]
---

# G02 软件实现与验证工作卡

## 1. 问题、范围与上游

按用户要求推进当前条件支持的G02。依据根AGENTS、prompts/G02-pwm-timing、acceptance草案及当前hardware-profile；沿用G00工具链/构建记录、G01 r2板端采集和最新负载已接记录。G00硬件契约、G01标定并未整体通过，独立软件工作继续；本卡不执行带能量/示波器实验，不冻结正式台架判据。

聊天cwd“综合实验”已不存在，实际项目为 `D:/ADMIN/Desktop/WEIJI/zonghe`。在可写临时副本实现和验证，按修改前哈希回写；现有G01等未提交工作保留。候选源码/镜像为g02-sw-r1，最后已烧录镜像仍为g01-sw-r2；未下载新镜像。

## 2. 实现、行为与配置

- G02.1：显式调用公共时钟配置；中心对齐PSC0/ARR2000/RCR1，CCR1000为PA9逻辑50%。N6 TIMG使用SYSCLK/TIMPRE，运行时读回400MHz TIM和64MHz ADC才允许诊断。Release继承FSBL，推导不能代替实测。
- G02.2：纯C控制状态机与STM32端口分离；两阶段启动允许prepare期间STOP/fault取消；两路CC2一起准备后MOE放行。默认PA9/PF7为GPIO LOW、继电器命令LOW；两target的G02_ALLOW_PIN_OUTPUT均为0，无自动启动。STOP先撤销MOE/AOE、IRQ/计数/通道并恢复引脚LOW，故障锁存，显式清除仅回STOP。Error_Handler和6个CPU异常入口接入硬停。LOW不等于已验证的驱动/继电器关断。
- G02.3：显式诊断期间ADC1独占，TIM1更新触发；ADC完成、OVR、错误、UEV服务数、周期间隔、ISR软件耗时、CCR请求/后续2次UEV观察存入内存；128事件环形记录明确覆盖计数。OVR/ADC错误、持续缺完成和继电器ODR互锁异常停机锁存。成功清理后恢复G01软件触发；清理失败保持占有。ADC2不启动。
- 修复审查发现的边界：中心对齐DIR只读，重启先退出CMS再清DIR、恢复中心对齐；被拒的重复START不改变运行窗口。CCR仅写预装载，不用UG/UDIS打断触发节奏。
- 入口与测量清单：[G02软件契约](../../../instructions/specs/G02-pwm-timing.md)。调试mailbox只作本地诊断，未增加G05串口控制。10秒上限是软件观察窗口，不是已确认功率安全时限。

## 3. 验证与证据

| 检查 | 实际结果 | 原始/派生证据 |
|---|---|---|
| 生产状态机故障注入 | GCC严格警告编译，10组通过，exit0 | checks-02/control.stdout及checks.json |
| 生产端口/HAL寄存器模型 | 默认gate与pins-enabled模拟两个分支均通过，exit0 | checks-02/default.stdout、pins-simulated.stdout |
| 竞争与停止边界 | prepare期间STOP/fault、启动各步失败、互锁、清理失败、重复init、DIR只读、缺ADC完成、CCR2UEV、BUSY窗口不变 | tests/g02源码与checks-02日志 |
| G01回归 | 生产C故障注入、16项Python检查、36条/9通道合成回放通过，exit0 | g01-regression-02/checks.json及raw/derived回放 |
| Release干净构建 | 0错误0警告，exit0，ARMClang6.24 | raw/BMS_EX_Release-r2.log |
| Debug干净构建 | 0错误1条原有L6314W EXTRAM警告，exit1 | raw/BMS_EX_Debug-r2.log |
| HEX独立检查 | 全记录校验和正确、无重叠、payload匹配BIN；Release起址0x70100400、Debug0x34000400 | build-results.json |

命令完整参数及退出码在checks.json/build-execution.json，含使用 `UV4 -r … -t … -j0 -o …` 的实际路径。静默选项依据[Keil官方命令行文档](https://www.keil.com/support/man/docs/uv4/uv4_commandline.asp)。首轮Release-01在沙箱无法启动ArmLink，工具安装文件实际存在；正常用户环境静默重试成功。checks-01的C用例已通过，但报告生成遇Python3.8相对路径错误；修正后checks-02完整通过，旧尝试保留。

候选HEX/AXF/BIN/MAP归档firmware-final（firmware保留元数据版本对齐前的中间产物）；before保存本次改动前文件；changes.diff只归属本次修改，不将旧工作树变化算入本任务。source-manifest与源码快照固定实际输入；manifest单独区分候选镜像与actually_flashed=false。工具/原始证据/源码哈希支持追溯，不代表硬件性能。

## 4. 判定与放行范围

本卡约定的实现、构建、离线验证和测量准备完成；G02阶段仍in_progress，正式verdict=null，G03不放行。判据草案中100kHz/50%是设计目标，频率/占空比误差、10秒计数、有效死区和停止期限都没有新的bench结果。

UEV计数是ISR服务次数，UIF可合并；ADC计数是已处理完成，STOP边界可能留有UIF/在途转换。CCR两UEV记录为保守软件观察界，DWT记录不含IRQ进入前延迟或驱动传播。寄存器模型不模拟真实预装载、ADC跨域或电气波形。调试暂停时TIM未配置freeze，不能用halt/单步证明连续时序或STOP期限。CPU异常首步硬停早于状态记账，普通STOP的DWT区间不能代表CPU异常的端到端延迟。

## 5. 未执行条件与下一步

缺少本次功率禁能接线、负载/模拟源实际输出状态、继电器LOW物理含义、驱动有效电平/供电、PA9/PF7实物测试点、探头参考方式、有效死区和停止期限。hardware-profile保留未知值，没有从课程示例填硬限。

下一步为G02.4准备：确认并登记无功率接线与探头/测点，在具体烧录及测试授权下建立新run；先验证默认态、STOP，再采PA9/PF7的50%与另一CCR点、驱动/Vgs及ADC同步窗口。各用例保存原始波形和设置，结果按软件/MCU逻辑/驱动分别判定。运行时钟、连续计数、实际停止和Release冷启动均留待新镜像实测。
