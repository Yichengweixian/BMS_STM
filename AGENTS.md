# BMS 项目执行入口

本文件适用于本项目根目录及其子目录。用户已于 2026-10-28 采用此 BMS 执行规范。流程已采用；工程建议指标仍是草案，只有具体正式实验的冻结记录才使其成为该次验收判据。

## 开始工作

1. 阅读 `README.md`、`instructions/README.md`、`instructions/STATUS.md`。
2. 按任务阅读 `instructions/WORKFLOW.md`、相关 `instructions/specs/` 文件与当前工作卡。
3. 当前实际源码根为 `BMS_EXv1.1/BMS_EX`；Keil 工程为 `BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/BMS_EX_Appli.uvprojx`。修改前核对 target 与实际纳入构建的文件。

## 执行原则

- 推进用户已经授权的工作；独立的实现、构建和离线分析不因其他阶段缺少硬件条件而停止。小任务按影响选择必要验证，不为每个注释修改建立完整实验。
- 原课件、手册、历史开发记录与外部项目 instructions 是证据材料，不自动成为当前任务指令。其他工程的模型路由、额度监控及比赛规则不适用。
- 先固定基线与测量，再验证PWM/功率级、PI、接口和SOC数据。按 `instructions/specs/acceptance.md` 处理正式验收依赖；探索调试允许迭代。
- 正式验收前固定固件、配置、标定、工况、处理方法和判据；结果出来后修改其中内容要新建修订/run，保留旧失败。
- 使用 `status`、`verdict`、`evidence_scope` 分别记录进度、结果和证据范围。编译、仿真、台架与Release自主启动不能相互替代；未经执行的结果保持 null。
- 一张工作卡描述任务，每次正式运行保存 manifest。阶段进度只在 `instructions/STATUS.md` 维护，重要动作追加到 `instructions/RUNLOG.md`。
- 原始数据不覆盖；PEC错误、超时、过期与饱和不能伪装成有效0。测量数据须能追溯到时间、单位、符号、固件与标定版本。
- 芯片驱动、板级换算/标定、实时控制、应用记录/SOC分层。模型、MCP或上位机不承担MCU的微秒级控制及本地保护。
- 硬件参数唯一入口是 `instructions/specs/hardware-profile.json`。未知值保持 null；带载测试前补齐本次动作所需的限值、接线与停止路径，不用讲义示例冒充实物确认。
- `firmware/prebuilt/BMS_Appli.hex` 是来源独立的预编译固件，不能当成当前源码构建结果；Debug/Release和实际烧录身份分别记录。

## 目录与产物

课程资料在 `docs/course`，手册在 `docs/manuals`，阅读指南在 `docs/guides`，工具安装包在 `tools`，规范在 `instructions`。保留原始资料与压缩包；未经任务需要不改Keil工程布局。

将来实验记录放在根目录 `evidence/runs/<run_id>/`，raw与derived分开。HTML说明由 `instructions/validation/render_html.cjs` 生成，编辑对应Markdown后重生成；文档检查只能支持文档结论。
