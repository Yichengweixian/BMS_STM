# BMS 执行规范 · 项目执行版

建立于 2026-10-28，并于同日按用户要求放入项目 `instructions/`。项目根 [AGENTS.md](../AGENTS.md) 已采用本流程；E类工程建议指标仍为待冻结草案，H类实物限制仍须确认。适用于 STM32N6 + ADBMS1818 + 双向 DC-DC 课程工程，**不代表固件已补全、已烧录或硬件验收通过**。项目目录入口见 [根README](../README.md)。

先读 [问题解答与实施路线](guide.md)，也可打开同目录的 `BMS实施与验收指南.html`。然后读 [验收标准](specs/acceptance.md)、[测量分层](specs/measurement.md)、[数据规范](specs/data.md)。

## 如何使用

1. 从 [当前状态](STATUS.md) 找到下一阶段，先处理 [待确认项](references/open-questions.md) 中影响该阶段的项目。
2. 用 [工作卡](templates/work-card.md) 记录问题、实现、方法、验收判据与结果。调试允许迭代；正式验收前固定待测版本、方法和判据。
3. 正式运行复制 [运行清单](templates/run-manifest.json)，生成唯一 `run_id`。原始数据、波形和参考仪器记录一起保存。
4. 按判据复算结果，登记 `status`、`verdict`、证据范围。失败保留，新修订新运行；不改写旧结果。
5. 只在 STATUS 维护阶段状态；RUNLOG 追加改变判断的重要动作。硬件参数在 [hardware-profile](specs/hardware-profile.json) 维护，不到处复制常数。

## 文件用途

| 文件 | 用途 |
|---|---|
| guide.md / BMS实施与验收指南.html | 解释 ADC、换算、开环/闭环、SOC 及实施次序；HTML 为阅读版 |
| MIGRATION.md | 旧 instructions 哪些保留、简化、删除与替换 |
| WORKFLOW.md | 调试、正式验收、状态、版本和失效范围规则 |
| STATUS.md / RUNLOG.md | 当前阶段与关键过程记录 |
| ../AGENTS.md / AGENTS_BMS.example.md | 当前项目代理入口 / 已采用情况说明；不再使用示例中的另一套规则 |
| specs/measurement.md | 驱动、换算、标定和应用算法职责 |
| specs/acceptance.md | G00—G07 的前置、指标、证据和失败处理 |
| specs/data.md | 时间戳、原始数据、SOC 标签与训练集规则 |
| specs/hardware-profile.json | 实际硬件边界，未知项保留 null |
| templates/work-card.md | 小任务五部分合一的记录模板 |
| templates/run-manifest.json | 每次验收的版本、固件、仪器、判据和证据入口 |
| templates/calibration-record.json | 各通道标定系数、拟合点和独立验证点 |
| references/open-questions.md | 未知项、解决证据、阻塞范围 |
| references/source-map.md / source-manifest.json | 依据定位及本次读取资料的 SHA-256 快照 |
| references/layout-migration.json / history/ | 目录整理前后路径、原始文件哈希及旧版说明快照 |
| validation/render_html.cjs | 从说明文件生成离线 HTML，编辑内容后重新运行 |
| validation/check_bundle.py | 检查 JSON、内部链接、模板和哈希快照；不测试硬件 |
| validation/structure-report.json | 上述检查器实际执行生成的报告 |
| validation/review_html.cjs / html-report.json | 桌面/手机布局、章节导航与链接检查及实际报告 |
| validation/desktop.png、acceptance.png、mobile.png | HTML 阅读效果检查截图，不是硬件实验截图 |

外部 `D:/ADMIN/Desktop/instructions` 仅作为流程设计参考，保持原样。其赛题、模型路由、额度监控、截止时间不适用于此 BMS 任务。采用本流程没有执行硬件实验，也没有启用 MCP。
