# Gitee PR #45 AI 评审登记（system-clipboard 分支）— 2026-10-02

> 来源：Gitee PR #45 评论
> [`note_51427764`](https://gitee.com/jermaine/yate/pulls/45#note_51427764_conversation_191310328)，
> AI 队友（pull_review_bot_2f642dd39f557e6f）2026-10-02 10:20:26 完成
>（触发评论 `note_51427763`，10:13:56）。
> 评审对象：PR #45 全量 diff——分支 `feat/system-clipboard` 的系统剪贴板
> 集成（新增 `yate/services/clipboard.py` 服务模块与
> `typings/pyperclip/__init__.pyi` 类型桩、`editor_core/buffer.py` 命名
> 寄存器参数化改造、vim 键位剪贴板同步与命名寄存器支持、
> vsc 键位（Ctrl-X/C/V）全量同步系统剪贴板、中英文手册更新）。

## 一、四维度结论

| 评审规则 | 结论 |
|---|---|
| 功能性与逻辑 | ⚠️ 待优化 |
| 安全性 | ✅ 通过 |
| 性能 | ✅ 通过 |
| 可维护性 | ✅ 通过 |

**总体结论**：⚠️ 无阻断项，发现 1 个改进建议，可优化后合并。风险等级 medium。

**风险与影响（评审原文摘要）**：主要影响功能性——在只读缓冲区使用 Ctrl-V
粘贴时，编辑器会正确提示只读并拒绝插入，但内部 unnamed 寄存器已被系统剪贴板
内容意外覆写，用户丢失之前 yank 的内容；vsc 与 vim 两套键位在同一 PR 内
语义不对称。安全性、性能及可维护性表现良好，无其他阻塞问题。

## 二、改进项（1 项）

### 1. vsc paste 动作在只读缓冲区上污染 unnamed 寄存器（功能性与逻辑）

- **问题**：`yate/actions.py` 新增的 `paste` 动作在调用 `buf.paste()` 之前
  先执行 `buf.register = text`；缓冲区只读时 `buf.paste()` 抛出
  `BufferReadOnlyError`，粘贴失败但 unnamed 寄存器已被系统剪贴板内容覆写
  ——与旧行为（不动寄存器）及 vim 侧 `_prime_paste` 的防护逻辑不一致。
- **修法（评审建议）**：写入寄存器前增加只读检查，与 vim 侧 `_prime_paste`
  对称，避免在即将失败的操作中产生副作用（`if text and not buf.read_only:`）。
- **处置**：✅ 已修（2026-10-02，`64f5eeb`）：`read_only` 守卫 + docstring
  说明 + 回归用例
  `test_paste_action_on_read_only_buffer_does_not_prime_register`（断言只读
  缓冲粘贴抛 `BufferReadOnlyError`、寄存器保持原值、剪贴板读取恰好一次）。

## 三、处置状态

- ✅ **已闭环**（2026-10-02 登记 + 当批修复）：唯一改进项已修（`64f5eeb`）。
  合并 master（`a0aa796`）后全量门禁复验：pytest 退出码 0（含新回归用例）、
  pyright strict 0 诊断。
- 登记轨迹：本文件 + [README.md](README.md)（速览 #18、轮次总表各一行）。
  编号说明：速览 #17 已由 py-style-audit 分支的 PR #44 评审登记占用
  （文档 `2026-10-02-pr44-py-style-audit-review.md`，随该分支合并后与本
  文件同目录），本分支顺延取 #18，两分支合并后编号连续不重复。

---

## 第二轮评审（2026-10-02 14:10，comment [`note_51428848`](https://gitee.com/jermaine/yate/pulls/45#note_51428848_conversation_191310328)）

> 首轮修复（`64f5eeb`）与合并 master（`455948e`）推送后触发复审。

### 四维度结论（第二轮）

| 评审规则 | 结论 |
|---|---|
| 功能性与逻辑 | ⚠️ 待优化 |
| 安全性 | ✅ 通过 |
| 性能 | ⚠️ 待优化 |
| 可维护性 | ⚠️ 待优化 |

**总体结论**：⚠️ 无阻断项，4 个改进建议，风险等级 low。历史项「vsc paste
覆写只读缓冲区 unnamed 寄存器」被评审确认已在 `64f5eeb` 闭环。

### 改进项（4 项）与处置

1. **`pending_register` 在非操作符命令后未清理**（功能性与逻辑，
   `yate/keymaps/vim.py`）：`"a` 后执行 `x`/`u`/`J`/`o` 等无关命令后前缀
   残留，后续一次 `yy` 被静默写入命名寄存器 a 且不镜像剪贴板。
   ✅ 已修（本批）：`_handle_normal` 全部非消费分支显式清理——`x`（含注释
   说明动机）、`u`/ctrl-r/`J`/页键、`/`/`?`/`:`、`n`/`N`、extension 绑定与
   未映射吞没的统一清理点；插入入口既有 `_enter_insert` 清理覆盖。
   回归用例 `test_register_prefix_does_not_survive_an_unrelated_command`
   （`"ax`→`yy` 落 unnamed + 镜像、`named_registers` 为空）。
2. **「空串不写系统剪贴板」守卫仅存在于 `_mirror`**（功能性与逻辑）：
   `_store_deleted` 与 `actions.cut`（两处）/`actions.copy` 无条件调用
   `copy_text`。✅ 已修（本批）：三处补真值守卫——空串仍写内部 unnamed
   寄存器，仅跳过剪贴板；守卫钉用例
   `test_visual_delete_with_empty_result_never_touches_clipboard`（经公开
   键位路径 + 实例桩模拟空删除结果；真实按键路径下空串近似不可达，
   actions 侧守卫同此理由不设牵强用例）。
3. **vsc `paste` 只读缓冲区仍先读系统剪贴板**（性能，`yate/actions.py`）：
   与 vim `_prime_paste` 不对称（后者只读时零读取）。
   ✅ 已修（本批）：`read_only` 检查前置，只读粘贴零剪贴板系统调用；
   回归断言同步为 `pastes == []`。
4. **缺「后端不可用时按键路径不抛异常」键位层用例**（可维护性）。
   ✅ 已钉（本批）：`_FakeClip.copy_result` 可失败，新增
   `test_yy_survives_unavailable_clipboard_backend`（`yy` 不抛异常、
   unnamed 寄存器正常填充），将设计目标 §二.3 降级语义固化到键位层。

### 第二轮处置状态

- ✅ **已闭环**（2026-10-02）：4 项全部处置（3 修 + 1 钉）。方案文档：
  [clipboard-review-round2-fixes-plan.md](../documents/clipboard-review-round2-fixes-plan.md)
  （含否决路线与实施偏离记录）。门禁：pytest 全量退出码 0、
  pyright strict 0 诊断。

---

## 第三轮评审（2026-10-02 19:07，comment [`note_51430464`](https://gitee.com/jermaine/yate/pulls/45#note_51430464_conversation_191324690)）

> 第二轮修复（`ec2606e`）推送后触发复审。

### 四维度结论（第三轮）

| 评审规则 | 结论 |
|---|---|
| 功能性与逻辑 | ⚠️ 待优化 |
| 安全性 | ✅ 通过 |
| 性能 | ✅ 通过 |
| 可维护性 | ✅ 通过 |

**总体结论**：⚠️ 无阻断项，2 个改进建议，风险等级 medium。评审认可
「经过两轮评审修复后，整体质量较高」。

### 改进项（2 项）与处置（用户决策：登记不修）

1. **vsc `cut` 动作的原子性**（功能性与逻辑，`yate/actions.py:102-118`）：
   先 `buf.register = buf.selected_text()` 后 `delete_selection()`，只读
   缓冲区上删除抛 `BufferReadOnlyError` 时寄存器已被污染——与首轮 paste
   问题同类（先写寄存器、后失败），vim 侧 `_store_deleted` 为「先删除再
   写入」的相反顺序。⏸ **明确不修**（2026-10-02 用户决策，登记留档）；
   如后续调整只读交互契约（见第 2 项），可一并重审两处动作的失败语义。
2. **vsc `paste` 只读缓冲区建议静默返回**（功能性与逻辑，
   `yate/actions.py:142-146`）：评审建议去掉 `buf.paste()` 的只读抛错、
   改为提前 return。⏸ **明确不修**（2026-10-02 用户决策，登记留档）。
   登记备注：现行契约是只读操作显式抛 `BufferReadOnlyError` 由调度层
   通知用户（与 vim 键位只读拒绝路径一致），静默返回会把失败降级为
   无反馈 no-op；且回归用例
   `test_paste_action_on_read_only_buffer_does_not_prime_register`
   已锚定抛错语义——采纳建议需先推翻该契约，非本项「开销」层面的
   小改动。

### 第三轮处置状态

- ⏸ **登记即止**（2026-10-02）：2 项均按用户决策不修复，无提交、
  无门禁变更；此前两轮修复与门禁状态不变
  （`64f5eeb` + `ec2606e`，pytest 退出码 0、pyright strict 0 诊断）。
