# ext-enh-review-fixes-plan.md — 扩展系统增强分支评审修复方案

> 来源评审记录：[../reviews/2026-10-13-extension-system-enhance.md](../reviews/2026-10-13-extension-system-enhance.md)
> 分支：`enh/extension-system-enhance`（worktree `yate-extension-system-enhance`）
> 日期：2026-10-13

## 一、目标与非目标

**目标**：修复两轮评审（code-review-expert + pr-review）合并后的
[CRITICAL]/[WARNING]/[MINOR] 发现，复跑全量门禁并回填证据。

**非目标**：不改事件/扩展 API 的对外语义；不做性能预优化；不动文档结构
（发现若涉文档仅做同步修订）。

## 二、备选方案与否决理由

- **方案 A（采纳）**：小步修复——每条发现一个独立最小 diff，保持既有设计
  （EventHub 同步派发、拉取模型、A13 回滚）不动。理由：评审结论全部为
  minor 级（无 blocker/major，若子代理报告升级则回 §四迭代重设计），
  零架构收益的重设计违反 plan-before-execute §三"不为假设性需求加抽象"。
- **方案 B（否决）**：为 `EventHub` 增加消息去重/聚合层。理由：为罕见多败
  场景造抽象，违反"能用函数实现的就不造类"；登记观察即可。
- **方案 C（否决）**：`set_theme` 早退保留、补文档说明消息丢失。理由：
  确认消息是既有用户可见行为，附带丢失属回归，修行为优于记档。

## 三、分步实施计划

### Step 1：`set_theme` 同值守卫只包事件发射（pr-review MINOR-1）

- 输入：评审记录 §1.2 MINOR-1
- 改动文件：`yate/editor.py`
- 做法：删除 `if name == theme.active().name: return` 早退；在
  `self.events.emit(EditorEvent.THEME_CHANGED, ...)` 处加同值守卫
  （`if name != theme.active().name` 或等价布尔），消息行保持原样。
- 输出：重复 `:theme <当前>` 恢复输出 `theme: <label>`，且不发事件。
- 验收命令：
  `.venv\Scripts\python.exe -m pytest tests/test_extensions.py tests/test_ui_contributions.py -q`
  以及下述 Step 4 全量门禁。

### Step 2：keymap 目标解析去重（pr-review MINOR-2）

- 输入：评审记录 §1.2 MINOR-2
- 改动文件：`yate/services/extensions/api.py`
- 做法：提取私有辅助（函数，不造类）：`_keymap_targets(keymap) ->
list[str]` 与 `_keymap_or_none(target, caller) -> Keymap | None`
（unknown 时 `log.warning` 列出注册名并返回 None），三处调用点收敛。
- 输出：`bind_key` / `bind_action` / `unbind_key` 无重复解析块；行为不变
  （现有测试不改断言）。
- 验收命令：`.venv\Scripts\python.exe -m pytest tests/test_extension_api.py tests/test_extension_bridges.py tests/test_lua_extensions.py -q`

### Step 3：shadowing 判定 resolve 防御（pr-review MINOR-3）

- 输入：评审记录 §1.2 MINOR-3
- 改动文件：`yate/services/extensions/loader.py`
- 做法：`owner.path.resolve()` / `record.path.resolve()` 包 try（OSError 时
  视为不同路径并照常上报 shadowing——保守侧），与 `load_file` 的防御一致。
- 输出：异常路径不再可抛。
- 验收命令：`.venv\Scripts\python.exe -m pytest tests/test_extensions.py -q`

### Step 4：合并子代理发现后的修复（预留）

- 输入：code-review-expert 报告（回填后按严重程度排序逐条处置）
- 改动文件：以报告为准
- 验收命令：§四全量门禁

### Step 5：收尾门禁与回填

- 主代理亲跑：
  1. `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/`（0 诊断）
  2. `.venv\Scripts\python.exe -m pytest tests/ -q`（全绿）
  3. `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q`
  4. `.venv\Scripts\python.exe -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75`
  5. `.venv\Scripts\python.exe -m tools.smoke_test run`
- 回填评审记录 §一.1 门禁表与 §三修复记录；提交
  （`fix(extensions): ...` / `docs(reviews): ...` 按 git-commit-message.md）。

## 四、风险清单与回滚

- 风险：Step 1 改变 `set_theme` 控制流——已有 THEME_CHANGED 同值不发射的
  语义必须保住（有测试背书则复跑确认；无则补一条）。
- 风险：Step 2 重构键位解析——纯机械收敛，靠既有 bind/unbind 测试兜底。
- 回滚：单 commit per step，`git revert` 即可，无数据迁移。

## 五、执行波次

Step 1–3 文件互不重叠，可一批完成；Step 4 依赖子代理报告；Step 5 收尾串行。

## 六、执行记录（2026-10-13 收尾回填）

- **Step 1–3**：已执行（前序会话落盘，本次续作按"只认落盘结果"纪律复现验证：
  定向子集 112 passed / exit 0）。
- **Step 4**：code-review-expert 重派报告回收（首轮成员判死，变更配置后重下派，
  详见评审记录 §二），W1 与 pr-review MINOR-1 同源确认；S1–S6 全部采纳处置：
  S2/S3/S4/S6 直接修复，S1 采纳方案①（`StatusSegment` 纳入门面，冻结面
  13 → 14 名，四处同步），S5 规则名单行数同步（933 → 983，守卫口径实测）。
- **Step 5**：主代理亲跑全量门禁（均 exit 0）：pyright 0 诊断；全量 pytest
  单跑全绿；架构测试 31 passed；覆盖率 **91.95%**（≥75）；冒烟
  **112/112 scenarios、1352/1352 checks**。结果同步回填评审记录 §一.1/§二/§三。

### 偏离记录

1. **提交粒度**：Step 1–3 的修复在前序会话已落盘但未提交，与 Step 4 的
   S2/S3/S4/S6 修复在 `api.py` / `test_events.py` 上文件重叠，hunk 级拆分
   不可靠——两轮代码级修复合并为一笔 `fix` 提交（S1 门面化独立成笔，
   文档回填独立成笔），未按"每步一笔"机械执行。
2. **S1 选型**：子代理给出的方案①（纳入门面）被采纳而非方案②（文档声明
   例外）——手册引用成员按 python-coding-style §1.2 即开放 API，开放 API
   应落在冻结门面上；`UiExtensionBridge` 仍留给 `EXTENSION_SUBMODULE_FROZEN`
   白名单（statusbar 注入注解），门面 14 名口径已在规则/守卫/手册/冒烟四处
   对齐。
3. **MINOR-4 维持登记不动**（与方案 B 否决理由一致）。
