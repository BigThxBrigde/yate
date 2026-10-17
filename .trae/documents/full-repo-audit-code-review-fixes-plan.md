# full-repo-audit-code-review-fixes-plan

- 来源评审记录：[`../reviews/2026-10-17-full-repo-audit-code-review.md`](../reviews/2026-10-17-full-repo-audit-code-review.md)（互链）
- 上游语义来源：同分支两轮审计记录
  [`../reviews/2026-10-17-repo-structure-layering-audit.md`](../reviews/2026-10-17-repo-structure-layering-audit.md)、
  [`../reviews/2026-10-16-full-repo-audit.md`](../reviews/2026-10-16-full-repo-audit.md)
- 分支：`enh/full-repo-audit`（worktree `../yate-full-repo-audit`）
- 日期：2026-10-17
- 闭环环节：本文件即【方案】产物；经用户批准后进入【执行】

## 一、目标与非目标

**目标**：修复分支合入前 code review 确证的 **1 个 MAJOR（C-1）+ 4 个 MINOR（C-2～C-6）
中的 5 条**——即 C-1 / C-2 / C-3 / C-4 / C-5 / C-6 全部六条，逐条见评审记录 §三。
全部为**规则文本一致性 / 文档可复现性 / 代码整洁度**级改动，零行为语义扩展。

**非目标**：

- 不新增架构规则、不新增守卫用例集合（§六 用例数维持 **32**）；
- 不做 `editor_view/` 子域拆分、`editor.py` 拆分、`tools/pack` 更名（审计 S-3 / S-5 / S-9 仍为另案）；
- 不改 `subagent-workflow.md` 模型表（本轮【审核】的 GLM-5.3-Flash 仅在任务书内指定）；
- 不修 `Temp/yate_audit/` 临时探针指向的 tab 点击功能缺陷（本轮范围外，见 §五 偏离登记）。

## 二、发现到改动映射（证据见评审记录）

| 编号 | 级别 | 改动目标 | 改法 |
|---|---|---|---|
| C-1 | MAJOR | `.trae/rules/architecture-boundaries.md` §一 依赖连线图（`:47-94`） | 图内补**虚线**边 `EV -.-> EXTF`（标注"R14 已登记例外——全仓唯一向上连线"）；`:47-48` 措辞由"全部严格向下"改为"除下图标注的唯一登记例外（虚线）外严格向下"，并附例外文字说明（对应 `:210-214` R14 登记） |
| C-2 | MINOR | 同文件 §六 R12 条目（`:391-393`） | UI-free L0 清单补 `dist_meta.py`，与 `:367` R4 行、`UI_FREE_FILES` 三处对齐 |
| C-6 | MINOR | 同文件 §一 L4 行（`:16`）与 L0 行（`:31-41`） | L4 行补 `__main__.py`（`python -m yate` 入口 shim，`:1-8`，守卫 `_LAYER_RANKS` 已按 L4 计）；L0 行补 `yaterc.py` / `yaterc_options.py`（守卫默认 L0，R4 `:105` 与 `UI_FREE_FILES` 已收） |
| C-3 | MINOR | `tests/README.md:13-17` | 分母/分子改为**同源同口径**并写明口径：`yate/` 共 **140** 个 `.py`（含 `__init__.py`）、其中 **124** 个非 `__init__` 模块、**94** 个无非同名 `tests/test_<name>.py` |
| C-4 | MINOR | `yate/editor_term/emulator.py:674-680` + 其测试 | 钳制上界由屏高改**滚动区域高** `self.scroll_bottom - self.scroll_top + 1`；测试补窄区域（DECSTBM）场景 + 计数断言锚定语义 |
| C-5 | NIT | `yate/keymaps/keys.py` 文件尾 | 去掉 2 个尾空行，收敛为单尾换行 |

## 三、备选方案与否决理由

- **C-1 备选（否决）**：不改图，仅改 R14 措辞，声明"图注'未画出的一律禁止'不适用于
  已登记例外"。否决理由：该图注是**执法面**（与 §六 #32 `test_no_unregistered_upward_imports`
  配套），靠措辞豁免会让图丧失权威性，且图与条文继续互相否定；补一条虚线边是最小单点改法。
- **C-4 备选（否决）**：保留 `min(count, self.rows)`，仅把用例名改为
  `..._clamp_to_the_screen_height`。否决理由：钳屏高在窄区域下多做 `count - 区域高`
  次幂等空转（`_scroll_up(1)` 区域全空后无效果），语义仍错；改代码同为 1 行成本。
- **C-3 备选（否决）**：仅把 `139` 改 `140`、`92` 改 `93`。否决理由：`92` 按审计口径
  不可复现（实测同 worktree 两口径分别得 94 / 110），改后仍留不可复现数字；改为
  "分子分母同源 + 写明计数口径"，使后续审计可逐字复核。
- **调度备选（否决）**：把改动拆给两个并行子代理。否决理由：`subagent-workflow.md`
  §一.3 明确"子代理不得修改产品源码（`yate/`）"，本方案 6 条中有 2 条落在 `yate/`
  （`emulator.py` / `keys.py`）；且全部为 ≤5 行的单点改动，拆并发只增协调成本。

## 四、分步实施计划

```mermaid
flowchart LR
    S0["Step 0 记录+方案落盘<br/>(done)"] --> A["Wave A：规则文本<br/>C-1 / C-2 / C-6"]
    A --> B["Wave B：README + emulator + keys<br/>C-3 / C-4 / C-5"]
    B --> G["Step 3 全量门禁<br/>pyright + pytest + 架构 + 覆盖率"]
    G --> R["Step 4 审核<br/>code-review-expert（GLM-5.3-Flash）"]
    R -->|blocker / major| A
    R -->|无| F["Step 5 回填 + 分笔提交"]
    style A fill:#bbdefb,color:#0d47a1
    style B fill:#c8e6c9,color:#1a5e20
    style R fill:#fff3e0,color:#e65100
```

### Wave A — 规则文本一致性（C-1 / C-2 / C-6，同文件单写者）

- 独占文件：`.trae/rules/architecture-boundaries.md`
- 输入：§三 映射表 + 评审记录 §三 维度 A/B
- 输出：图为 17 条边（16 实线 + 1 虚线例外）；§一 L4/L0 行与 `_LAYER_RANKS` 逐名对齐；
  R12 清单与 R4 行逐名对齐
- 验收：`.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` → **32 passed**，exit 0
- 提交：`docs(rules): draw the registered L2->L3 exception and sync the inventories`

### Wave B — 文档可复现性 + 代码整洁度（C-3 / C-4 / C-5）

- 独占文件：`tests/README.md`、`yate/editor_term/emulator.py`、
  `tests/test_terminal_emulator.py`、`yate/keymaps/keys.py`
- 输入：评审记录 §三 维度 B/C
- 输出：
  1. README 计数按新口径改写（140 / 124 / 94），与命令输出逐字一致；
  2. emulator 两处钳制改用区域高；新增用例给"窄区域 + 超大 count"锚定——用
     `monkeypatch` 计数包装 `_scroll_up` / `_scroll_down`，断言调用次数 === 区域高
     （使"钳区域高"与"钳屏高"两种实现**可区分**）；
  3. `keys.py` 尾空行清除。
- 验收（逐项可复现）：
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_terminal_emulator.py -q
  .venv\Scripts\python.exe -m pyright yate/ tests/ tools/
  .venv\Scripts\python.exe -c "p='yate/keymaps/keys.py'; t=open(p,encoding='utf-8').read(); print(len(t)-len(t.rstrip(chr(10)))-1)"  # 期望 0
  ```
- 提交（分笔）：`docs(tests): restate the module count with one reproducible convention` /
  `fix(terminal): clamp scroll region count by the region height` /
  `chore(keymaps): drop the trailing blank lines in keys.py`

### Step 3 — 全量门禁（主代理亲跑，退出码全 0 才过）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q --cov --cov-fail-under=75
```

### Step 4 — 审核（本轮按 GLM-5.3-Flash 下发）

- 派 `code-review-expert`（任务书内显式指定模型 **GLM-5.3-Flash**）评审
  `git diff master...HEAD` 全部改动；结论须附实测结果与退出码；
- blocker / major → 回到 Wave A/B 迭代；仅 minor → 登记待办；结论回填本文件 §七。

### Step 5 — 回填与分笔提交

- 回填本文件 §七（真实前后数字、偏离记录）与评审记录 §四；
- 每 Wave / 每 Step 单独一笔提交，**只提交、不推送**（闭环内禁止 `git push`）。

## 五、风险清单与回滚

| 风险 | 缓解 / 回滚 |
|---|---|
| 改规则文本触发 §六 文本断言（如 `test_support_mouse_gate_lives_in_app_on_event` 等文本型守卫） | Wave A 后单独跑架构测试（32 passed）确认零误伤 |
| emulator 钳制改动影响既有 `test_scroll_up_and_down_commands` 等用例 | 仅改上界来源，全屏区域下 `rows == 区域高`，既有断言不变；Wave B 后单跑该文件全量用例 |
| `monkeypatch` 计数用例与并发 pilot 用例互相干扰 | Wave B 内串行执行；用例不用 pilot，纯 `TerminalEmulator` 实例 |
| README 计数再次漂移 | 改写后的两个数字均带可复制命令，后续审计可逐字复核 |
| 临时探针 `Temp/yate_audit/*` 指向的 tab 点击缺陷被误并进本轮 | 本轮**不触碰** `editor_view/`；该缺陷独立立项（见评审记录外的人工线索） |
| 回滚 | 每 Wave 单独 commit，`git revert` 单笔回滚；无数据风险 |

## 六、执行记录回填（待填）

- Wave A：待填
- Wave B：待填
- Step 3 门禁：待填（pyright / pytest / 架构 / 覆盖率 前后数字）
- Step 4 审核：待填（结论与退出码）
- 偏离记录：待填

## 七、偏离登记

- C-3 采用"口径改写"而非 `139→140 / 92→93` 的 ±1 修法，理由见 §三 第三条备选否决。
- 本轮全部改动由**主代理亲办**，未拆子代理，理由见 §三 调度备选否决；
  【审核】环节按用户口径派 `code-review-expert` 且指定 GLM-5.3-Flash（规则表不动）。
