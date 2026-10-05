# yate 代码评审报告：tcss 拆分实现（2026-09-27）

> 生成时间：2026-09-27 09:30 +08:00
> 评审对象：commit `3105f66`（feat(app): move app-level CSS to bundled app.tcss resource）+ 修复 `7e51d6b`，worktree `<worktree>`，分支 `enh/tcss-enh`（基线 master@479f192）
> 关联 issue：[IKINFT](https://gitee.com/jermaine/yate/issues/IKINFT)（ENH - 从 app 里面拆分 css 到 tcss 文件，集成打包）
> 评审范围：[yate/app.py](../../yate/app.py)、[yate/resources/app.tcss](../../yate/resources/app.tcss)、[tests/test_app_css.py](../../tests/test_app_css.py)、pyproject.toml（仅注释行）
> 评审方式：主代理多维评审 + 2 个子代理交叉验证（见 §六 诚实性说明）→ 主代理自审兜底；全部结论基于第一手 diff 与实测命令
> 计划文档：[tcss-split-plan.md](../documents/tcss-split-plan.md)（方案 A 选型、备选否决记录、8 步执行记录）

---

## 一、门禁与基线（实测数字）

| 门禁 | 结果 | 证据 |
|---|---|---|
| `pyright` strict（yate/ + tests/ + tools/） | **0 errors / 0 warnings / 0 informations** | 实现后与评审修复后各跑一次 |
| `pytest tests/`（Windows，venv 独立） | **exit=0**（pytest 9.1.1 起 `-q` 不再输出汇总行，以退出码为验收信号） | 实现后与修复后各跑一次 |
| 架构守护测试 | 13 用例含于全量 exit=0 | `tests/test_architecture.py` |
| pilot 冒烟（永久 runner） | `tools.smoke_test run`：**870/870 checks，83/83 scenarios**，76.8s | 含 `--svg` 文本提取 |
| smoke 基线 diff | `compare`：**81/83 MATCH**；2 处 DRIFT 经 master 逐字节复现定性为**存量**（见 §五） | exit 1 与本分支无关 |
| wheel 打包 | `pip wheel` 产物内含 `yate/resources/app.tcss`（zip 断言通过） | hatchling 自动收录 |
| PyInstaller one-folder | `pack.ps1 -SkipChangelog` 构建成功；`dist\yate\yate.exe --version` exit=0；bundle `_internal\yate\resources\app.tcss` 存在 | spec **零 diff** |
| CSS 等价性 | tcss 内容与原内联字面量逐行 diff 仅差首个空行（CSS 语义无关） | 程序化 difflib 比对 |

---

## 二、整体质量评分

| 维度 | 得分 | 依据 |
|---|---|---|
| 程序健壮性 | 9.5 / 10 | import 时 fail-fast（OSError + UnicodeDecodeError → 带路径的 RuntimeError）；一次性读取无资源泄漏；扣分：初版错误消息精度（已修） |
| 可扩展性 | 9.5 / 10 | 单点加载函数、无新抽象；CSS_PATH 升级路径在计划 §4.2 备案且文件本体不变 |
| 可维护性 | 9 / 10 | 与 `manual.py` 资源先例同构；docstring/注解/导入序合规；R2/R6/R8/R9 零触碰；扣分：初版 tcss 缺 R9 指针（已修） |
| 测试质量 | 9 / 10 | 两条不变量守卫（资源存在非空 + CSS 与文件一致，防回退内联）；pilot 全量回归佐证渲染零漂移 |
| **总评** | **93 / 100** | 0 致命 / 0 严重 / 3 建议（全部当场修复于 `7e51d6b`） |

---

## 三、核心问题清单（评审时状态，均已修复）

**未发现「致命 / 严重」级缺陷。** 3 个建议级问题：

### 1. 错误消息以 "is missing" 覆盖全部 OSError，且 `UnicodeDecodeError` 逃逸包装
- **位置**：[app.py:44-48](../../yate/app.py#L44-L48)
- **维度**：健壮性 / 可观测性
- **问题**：`PermissionError`、`IsADirectoryError` 等同为 `OSError`，报 "missing" 失准；`UnicodeDecodeError` 是 `ValueError` 子类不被捕获，资源损坏场景丢失指明路径的可行动信息（裸解码错误不含文件路径）。
- **后果**：打包缺陷/损坏场景下排障消息误导。
- **修复**（`7e51d6b`）：`except (OSError, UnicodeDecodeError)`，措辞改 "could not be read"，docstring 同步。

### 2. `app.tcss` 缺少 R9 同步指针
- **位置**：[app.tcss:1-3](../../yate/resources/app.tcss#L1-L3)
- **维度**：可维护性
- **问题**：CSS 从 `app.py` 迁出后，R9 "改 id 必须同步改 CSS" 的同步对象变为此文件，但文件自身无提示；在 `.py` 中全局搜 CSS 不再命中，未来改 id 者易漏改。
- **修复**（`7e51d6b`）：文件头 3 行 `/* */` 注释声明 id 冻结与同步义务并指向规则文档。

### 3. return 语句不必要折行
- **位置**：[app.py:43](../../yate/app.py#L43)
- **维度**：可维护性（风格一致性）
- **问题**：单行形式 87 字符，在项目 100 字符上限内，3 行折行属防御性噪声。
- **修复**（`7e51d6b`）：合并为单行。

### 已排除的候选（防误报记录）

- 「import 时读资源会破坏 `--version`/`--changelog`」—— 误报：[cli.py:193-206](../../yate/cli.py#L193-L206) 两分支均在惰性导入 `YateApp`（L308）之前返回。
- 「两个测试应抽 fixture 共享读取行」—— 拒绝：19 行文件重复 1 行，抽 fixture 反增样板，违背最小复杂度原则。

---

## 四、整改记录

| 提交 | 内容 | 修后门禁 |
|---|---|---|
| `7e51d6b` refactor(app): polish tcss loader after review | 上述 3 项一次修完（2 文件，+9/−8） | pyright 0 诊断；pytest exit=0（含 pilot UI 测试——带注释 tcss 的解析已在挂载路径验证） |

---

## 五、与本分支无关的存量事项（如实记录，超出本轮范围）

1. **master smoke 基线过期**：`compare` 中 `set_options_matrix` 的 3 个 readonly 检查项报 "new check"——readonly 功能（master `108f763`）落地后未重 snapshot。已在 master@479f192 上逐字节复现相同 DRIFT。建议：发布清单加入「功能合入后重 snapshot」。
2. **`stress_key_fuzz` 时序 flaky**：键序差异导致 saved 内容 diff，同样在 master 复现。遇此先重跑确认再下结论，不许直接改基线。
3. **pytest 9.1.1 输出行为变化**：`-q` 不再打印汇总行，CI/本地验收应以退出码为准（`pyproject.toml` 未锁 pytest 上限，属环境演进）。

---

## 六、诚实性说明

- 按交叉验证流程派出的 2 个验证子代理**均误读主仓目录**（`<worktree>`，master 无此变更），得出 "app.tcss 不存在" 的错误结论；修正路径重试时子代理已结束（SendMessage 返回 finished），按子代理规则的兜底路径转**主代理自审**：3 个问题均为确定性事实（语言语义、文件内容、字符数算术），无推测成分；子代理零产出已如实计入，不冒充交叉验证结论。
- 所有打包/门禁数字均为 worktree 独立 venv 实测（`.venv`：textual 8.2.8 / pytest 9.1.1 / pyright 1.1.414 / PyInstaller build extra），未引用任何子代理自述数字。
