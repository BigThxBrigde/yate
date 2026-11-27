# 2026-11-23 pr-review —— feature/enh-lsp-navigation（IKX5EP）

范围：merge-base `c6d6e89a7d5866ee98577a633211b0abf6ea2098` → HEAD `9b6f6471`；12 笔提交 / 38 个文件 +5011 −21（分支与 master 未分叉）。模式：`review`（完整六个维度 + 硬门禁）。两位只读 `code-review-expert` 评审者（功能/安全/性能 与 架构/可维护性/文档/合并就绪度）+ 主代理对每一发现项做证据复核。本环境未注册 `python-code-review` skill，因此评审者回退到各自的角色文件检查清单。

## 总体：REQUEST_CHANGES（基线）→ APPROVE（修复后）

基线：6 MAJOR / 8 MINOR，0 BLOCKER。所有 MAJOR 本轮闭合；1 个 MINOR（`positionEncoding` 未在既有 `client.py` 中协商，不在本 PR diff 内）登记为后续事项；其余 MINOR 均已修复或显式登记。基线时无硬门禁为红。

## 发现项与处置

### MAJOR —— 已修复

1. `yate/flows/lsp_navigation_flows.py:517-528` —— 对已锁定（分块）或只读 buffer 的重命名报告了虚假成功。`TextBuffer.replace_range` 在 `locked=True` 时静默无操作，但 `applied += len(edits)` 照常执行，于是尽管什么都没改，仍产出 `Renamed N occurrence(s)`。**修复**：`_check_edit_range` 现拒绝 `buf.locked` / `buf.read_only` / 反向区间；`_apply_workspace_edit` 拆为两阶段 —— 先做无副作用的预校验（拒绝时警告并返回，无需回滚），再执行应用 + 回滚。这也避免了对只读 buffer 回滚时抛出第二个 `BufferReadOnlyError` 而掩盖原始消息。回归用例：`test_rename_locked_buffer_...`、`test_rename_read_only_buffer_...`（修复前红、修复后绿）。

2. `yate/editor_lsp/navigation.py:247-249` —— `parse_locations` 接受了带 `uri` 但没有 `range`/`targetRange` 的字典；`_range_from(None)` 返回 `(0,0,0,0)`，flows 将其当作真实定义并跳到文件首行。**修复**：跳过 range 不是字典的条目。回归用例：`test_parse_locations_skips_entries_without_a_range`。

3. `yate/docs/lsp.en.md:38` / `lsp.zh.md:29` —— 将 `K` 记录为仅 vim 可用，但运行时探测显示 `VscKeymap` 与 `VimKeymap` 都会把 `<shift-k>` 解析为 `show_hover_docs`（`HOVER_POPUP_KEY`）。`manual.{en,zh}.md` §16 按键表只在 vsc 列列出 `F7`。**修复**：四处文档现均说明 `K`（vsc 为 `Shift+K`）在两种 keymap 下均可用。

4. `.trae/rules/architecture-boundaries.md:23-28` —— §一 的 L3 flows 枚举遗漏了 `lsp_navigation_flows.py`，而 §三.8 第 6 步要求同步它（该模块只出现在 R11 / §六）。**修复**：已加入 §一 L3 列表。

5. `.trae/documents/lsp-navigation-plans/lsp-navigation-guards-docs-plan-e.md:100-111` —— R11 称波次 4 的登记"已记录在计划中"，但执行记录只记录了 smoke-tag 偏差。**修复**：新增一条偏差记录，说明先导入后登记的时序以及最终 `UI_FROZEN_FILES` 的四模块清单。

6. `.trae/reviews/2026-11-22-lsp-navigation.md:3-4` —— 范围行写的是 33 个文件 / +4375 −19，而修复后终态为 38 / +5011 −21。**修复**：范围行现标注评审时与修复后的数字，并注明重新实测的提交。

### MINOR —— 已修复

- `yate/editor_lsp/navigation.py:485` —— `activeParameter` 仅从 `SignatureHelp` 信封中读取；按 `SignatureInformation` 逐项上报该值的 server 会高亮错误的参数。现优先取所选签名的值，并将负值钳到 0。已新增两个回归测试。
- `.trae/documents/lsp-navigation-plan.md:4`、`lsp-navigation-request-layer-plan-a.md:109`、`2026-11-22-lsp-navigation.md:3` —— 机器本地 worktree 路径已替换为相对占位符。
- `.trae/reviews/README.md` —— 已将本次评审登记为 #80（分支本地）。
- `yate/resources/manual.{en,zh}.md` §16 按键表 —— 修正了 vsc 的 `K` 列。

### MINOR —— 已登记（非阻塞）

- `yate/editor_lsp/client.py:602-641`（既有代码，不在本 diff 内）未声明 `general.positionEncodings: ["utf-16"]`；整条 UTF-16 列转换链都假设 LSP 3.17 的默认值。返回 `utf-8` 的 server 会静默错开非 ASCII 列。后续问题：显式协商编码，或在编码不匹配时将导航降级为不支持。
- `yate/flows/lsp_navigation_flows.py` —— 7 处重复的 `has_modal_screen()` 守卫（留待后续清理时抽取谓词）；`buf.anchor = None` 可改用 `clear_selection()`；LSP 跳转不会压入 jumplist；`navigation.request(client: Any)` 保留了一个显式的鸭子类型 `noqa`。
- 根目录下一个名为 `'` 的未跟踪文件源自评审前的 PowerShell 引号事故；它未暂存，应在合并前删除。

### 经证据撤回

- 评审者 B 的"vsc 只绑定 `F7`、不绑定 `K`"本身就是缺陷（文档有误）；运行时探测确定了正确方向。
- 评审者 A 关于 `_check_edit_range` 反向区间的主张起初受到质疑，后经阅读 `_delete_range`（在先前编辑之后抛错）得到确认 —— 已并入 MAJOR-1 修复。
- 评审者 B 的"`lsp_chooser` 中缺少 R15 滚动条"与"R10 重复绑定"已撤回：经确认基类接线存在且原始按键各不相同。

## 硬门禁（主代理，修复后，真实退出码）

| 门禁 | 结果 | 退出码 |
|---|---|---|
| `pyright yate/ tests/ tools/ pack/` | 0 errors | 0 |
| `pytest tests/ -q -n auto`（4046 tests，4036 passed，10 skipped） | 全绿 | 0 |
| `pytest tests/test_architecture.py -q` | 47 passed | 0 |
| `pytest tests/ --cov=yate --cov-branch -n auto` | 92.74%（≥75）、4036 passed / 10 skipped；此前 `test_app_find_replace.py` 的一次并行 flake 经 `-n 1` 复跑通过 | 0 |
| `tools.smoke_test run --jobs 4` | 128/128 场景，1554/1554 检查 | 0 |
| `tools.changelog check` | 已发布部分为最新；unreleased 滞后是生成器机制 | 0 |
| `git diff --check c6d6e89a...HEAD` | 无空白错误 | 0 |

注：`pytest tests/test_architecture.py` 有一次调用报告退出码 1，因为本机 safe-delete 钩子在测试收尾时拦截了 `%TEMP%` 批量清理（47 个测试全部打印 `PASSED`）；非测试失败。覆盖率中唯一一次并行失败（`test_app_find_replace.py`）同样是时序 flake，串行复跑通过。首次冒烟运行报告 127/128、有一项检查失败；立即复跑得到 128/128 / 1554 检查、退出码 0。三者均为负载敏感的环境伪影，已按仓库规则记录；上面权威的修复后结果是那些通过的运行。

## 第二轮 pr-review（2026-11-23，`e018cb1c..f1c4e8b4`）

第二位评审者重新审计了这两笔修复提交。基线：REQUEST_CHANGES，2 MAJOR / 4 MINOR。一次负向演练（将新测试移植到一次性 worktree 中的修复前 `9b6f6471`）使五个行为用例全部转红，确认这些测试并非同义反复。

- MAJOR（已修复）—— `navigation.py:249-253`：第一轮守卫只检查了 `range` 是否为字典；部分 range（`{"start": ...}` 或 `{"end": ...}`）仍会让 `_pos_from(None)` 捏造 `(0,0)`，恢复幽灵跳转。守卫现要求 `start` 与 `end` 都是字典；已新增回归用例 `test_parse_locations_skips_ranges_missing_an_endpoint`。
- MAJOR（已修复）—— 本报告与 `.trae/reviews/README.md` #80 引用了修复前的门禁数字（4029 passed / 92.81%）。已更新为终态实测值（含第二轮新增的两个用例）：4046 tests / 4036 passed / 10 skipped，92.74%。
- MINOR（已修复）—— `lsp_navigation_flows.py:521-529`：预校验失败时遗漏了出问题的文件名，而其它分支都包含 `path.name`；Phase-1 包装器现追加 `(<file>)`。已新增 `test_rename_multi_doc_prevalidation_is_atomic`，锁定多文档编辑遇到不可写目标时的零副作用契约。
- MINOR（已登记，不在本 PR 内）—— 通过 `replace_range` 回滚会留下一条撤销记录；本 PR 之前即存在，无害（内容与原始一致），并通过 Phase-1/PHASE-2 的 docstring 拆分加以说明。
- MINOR（已登记，master 基线）—— 冒烟 `stress_rapid_toggles` 在 `--jobs 4` 下负载敏感（127/128），在 `--jobs 1` 下全绿；与本 diff 无关，且已在 master 基线 flake 清单中。

## 亮点

- 能力降级区分 `no-ready-server` 与 `unsupported`，给出明确的用户消息且保持 buffer 不变。
- WorkspaceEdit 预校验 + 快照回滚，现对锁定/只读/反向区间做了加固；新打开的文件会披露为未保存。
- URI 缓存带失效机制、O(1) 诊断查找、按文档身份/路径/光标为键的异步请求取消 —— 无热路径回退。
- 47 个架构守卫（从 46 增加）覆盖新增的 flows 模块及两种 keymap 的共享导航键；双语文档与冒烟标签保持同步。
