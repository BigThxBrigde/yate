# readme-screenshots 评审记录（feat/readme-screenshots，2026-11-02）

> 评审对象：分支 `feat/readme-screenshots` 提交 `2e311e8..afcaf5f`（5 笔：
> 0d43285 工具 / 509f88f 截图+画廊 / 2acf2da README 链接 / 2a85b8a 游戏谓词
> 类型化 / afcaf5f 画廊语义修复）。
> 方案来源：[readme-screenshots-plans/overview.md](../documents/readme-screenshots-plans/overview.md)
> + plan-a/b/c。用户需求：全部 features + 工具 + 测试截图 → `screenshots/`
> → 画廊 MD → 根 README 链接。

## 一、执行结构（如实登记）

- `plan-architect-designer` spawn 两连败（模型未注册 `qwen-3.7-plus`，任务书
  指定模型无效）→ 按总纲 §一.3.5 主代理亲自规划；内置 `code-explorer` 中止
  （code=10003）→ 按 subagent-workflow §五.4 不原样重试，调研由主代理只读
  探针完成（SVG 确定性实证：同状态两次导出 sha256 一致）。
- `plan-executor`（executor-a）正常交付 plan-a：7 文件 +1129 行，验收三条
  退出码 0；主动探针实跑 22 个 pilot 场景；发现并修复 GBK 子进程编码缺陷
  （PYTHONIOENCODING=utf-8 + 录制 Console file=StringIO）。主代理独立复核
  通过后才提交（§五.3.2）。
- `code-review-expert`（reviewer）spawn 后两轮探活零回信、零产物、超 30 分钟
  窗口 → 判死（§五.3），主代理亲自按 code-review-expert 剧本评审（含强制
  自我批判环节），如实标注"评审子代理零产出"。

## 二、评审发现（自我批判后定稿）

| 级别 | 发现 | 位置 | 处置 |
|---|---|---|---|
| major（F1） | 画廊由「本次成功子集」渲染，`--only` 部分再生会把 `screenshots/README.md` 缩水为该子集；且 wave-2 提交的画廊实际只有 1 节——确定性抽查用旧代码跑 `--only welcome-screen` 覆写了全量画廊，主代理未复检即提交（双重根因：代码语义 + 流程漏洞） | `tools/screenshots/__main__.py`（原 :109-112） | 已修（`afcaf5f`）：画廊改为全量注册表 × SVG 存在性过滤，部分再生字节一致（实测 SHA256 前后相等），新增回归测试 `test_partial_regen_preserves_full_gallery` |
| minor → 不处置 | `Scenario.size` 为注册表元数据，运行器不消费（驱动内置 `_SIZE`） | `scenarios.py:59` | 保留：测试 `test_registry_names_are_kebab_and_unique` 断言消费，作为注册表自文档字段成立 |
| minor → 不处置 | 三个报告场景驱动多调一次 `write_fixtures`（夹具未被使用） | `scenarios.py:348/354/360` | 保留：统一"每个驱动先建夹具"的形态一致性，开销可忽略 |
| 不成立 → 删除 | 子进程命令注入面 | `cli_reports.py` | 命令列表全部硬编码、无外部输入进入 cmd，反证不成立 |
| 不成立 → 删除 | `except Exception` 静默吞错 | `__main__.py:105-107` | 有 `noqa: BLE001` 注释、逐场景打印失败原因、退出码 1——满足 §4.5"记日志或反馈"，非静默 |
| 不成立 → 删除 | 画廊 EOL 不确定（Windows CRLF / Linux LF） | `gallery.py:61` | 仓库 `text=auto` 归一，且实测部分再生前后 SHA256 相等（同机）；跨平台重排由 git 归一层消化 |

自我批判记录：初版还列出"stderr 合并进报告""报告驱动冗余 write_fixtures"两条，
反证后降级为观察项（报告截图本就是全量输出采样；形态一致性优先），不进处置清单。

## 三、门禁实测（主代理亲跑，CI 并行口径）

| 门禁 | 命令 | 结果 | 退出码 |
|---|---|---|---|
| pyright strict 全仓 | `python -m pyright yate/ tools/ tests/` | 0 errors / 0 warnings / 0 informations | 0 |
| 架构守卫 | `pytest tests/test_architecture.py -q -n 1` | 37 passed | 0 |
| pytest 全量 | `pytest tests/ -q -n auto` | 全绿（10 skipped） | 0 |
| 覆盖率 | `pytest tests/ --cov=yate --cov-branch -n auto` | 92.81%（门槛 75） | 0 |
| 冒烟 | `python -m tools.smoke_test run --jobs 4 --quiet` | 121/121 场景、1463/1463 checks | 0 |

## 四、产物抽查

- `screenshots/` 25 SVG（合计约 3 MB）；文件头均含 `rich-terminal`；
- 画廊 25 节与注册表一一对应、双语说明齐全、相对路径正确；
- README.md / README.zh.md 各 +8 行同构插入，其余零改动（diff stat 实证）；
- 确定性：`--only welcome-screen` 两次生成 SHA256 一致；部分再生后画廊字节不变。

## 五、已知限制（登记，不阻塞）

1. Nerd Font PUA 文件类型图标在无 Nerd Font 的查看端显示为方框（SVG-as-img
   不加载外部资源，画廊已说明）；
2. 报告类截图（smoke/pytest/pyright/diag）含真实运行的时间戳/耗时/计数，
   再生时数值会变；屏保截图采样一帧动画，位置随运行变化（画廊已说明）；
3. LSP 诊断标记截图未做（需真实语言服务器进程，无头环境 flaky）——补全弹窗
   场景以 buffer 单词回退语义如实呈现。

## 六、结论

**可合并**：0 blocker / 0 major（F1 当轮已修）/ 0 minor 待办；门禁五项全绿。
