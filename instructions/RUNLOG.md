# 关键过程记录

## 2026-10-28 · 规范适配

- 类型：documentation / static review。
- 输入：当前 BMS 工程、课程资料、外部 `D:/ADMIN/Desktop/instructions` 工作流模板、官方芯片与测量参考资料。
- 动作：建立 BMS 分层解释、G00—G07 验收草案、迁移说明、工作卡和运行/标定模板，记录待确认参数。
- 范围：新建当前项目内 `BMS执行规范`；未修改固件或外部 instructions；未烧录、未运行功率实验、未产生训练数据。
- 结论：可供下一阶段准备和审阅；全部硬件验收 verdict 仍为 null。结构检查以 validation/structure-report.json 的实际结果为准。

## 2026-10-28 · 目录整理与规范采用

- 来源：用户要求“整理项目文件夹，然后把新的instruction改了放到对应目录下面”。
- 目录：原 `BMS执行规范/` 改为 `instructions/`；课程、手册、阅读指南分别归档到 `docs/`；现成HEX到 `firmware/prebuilt/`；上位机、Flash加载器与安装包到 `tools/`。
- 入口：项目根新增README导航及AGENTS执行入口；流程采用，E类建议阈值仍待具体正式实验冻结。
- 保留：Keil工程 `BMS_EXv1.1/` 原路径与内容；外部旧instructions；所有原始压缩包与固件。旧说明及来源快照保存在 references/history。Office临时锁文件由Office管理。
- 追溯：references/layout-migration.json 记录路径映射、13份移动文件的前后哈希及432份Keil文件基线；validation/layout-report.json给出最终一致性与链接检查结果。
- 实验状态：没有构建、烧录、台架或模型实验；G00仍in_progress/null，其余阶段不变。

## 2026-10-28 · GitHub 初始同步准备

- 用户指定目标：`https://github.com/Yichengweixian/BMS_STM`；开始时远端为空，默认分支main。
- 本地建立Git仓库、origin、忽略规则与Git LFS；压缩包通过LFS传输，源码和资料保持原有内容。
- 文档适配：项目内部HTML文件链接改用相对路径；保留外部参考与历史快照的原始语义。
- 范围：仅版本管理与同步，不编译、安装、烧录或启动硬件实验。实际远端完成状态以Git提交和远端分支核对为准。
