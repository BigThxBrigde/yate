# yate Code Review — Gitee PR #38 评审（vscode 键位 review 分支）— 2026-09-29

## Gitee PR #38 评审（vscode 键位 review 分支）— 2026-09-29

> **范围**：PR #38 `review-vscode-keymap` → `master`（issue IKJ2V1「Review vscode keymap」：
> vsc 绑定全表核对 + vim/vsc 冲突排查 + ctrl-e/ctrl-shift-e 同字节去重修复 + 3 个防回归测试）。
> 本次登记 **Gitee AI 队友审查**（[原始评论](https://gitee.com/jermaine/yate/pulls/38#note_51409299_conversation_191192278)）：
> 结论 **⚠️ 无阻断项，可优化后合并**——功能性与逻辑 / 安全性 / 性能均 ✅ 通过，
> 可维护性 ⚠️ 待优化，风险等级 **low**（0 阻断 / 1 改进）。
> 分支方案与执行记录见 [review-vscode-keymap-plan.md](../documents/review-vscode-keymap-plan.md)。

### AI 发现逐条登记与处置

- [x] **改进项：重复键检测断言的诊断信息不足（可维护性，low）** —
  [`tests/test_vsc_keymap.py`](../../tests/test_vsc_keymap.py)
  `test_vsc_has_no_duplicate_raw_keys` 使用
  `assert len(keys) == len(set(keys))`，失败时 pytest 仅显示数量不匹配，
  **无法直接定位是哪个 raw key 发生了重复**——而该测试守护的恰是
  `Keymap._index` 静默覆盖（后者胜）这类难查缺陷，失败输出应直接点名重复键。
  审查者建议改用 `Counter` 显式列出重复项：

  ```python
  from collections import Counter

  def test_vsc_has_no_duplicate_raw_keys() -> None:
      """Every raw key appears once: ``_index`` must never silently override."""
      vsc = VscKeymap()
      counts = Counter(b.key for b in vsc.bindings)
      dupes = [k for k, c in counts.items() if c > 1]
      assert not dupes, f"duplicate raw keys found: {dupes}"
  ```

  *✅ 已修（2026-10-01，`3c1cee2`）——按评审给定 Counter 形态采纳：
  `test_vsc_has_no_duplicate_raw_keys` 改为 `Counter` 统计 + `dupes` 列表 +
  `assert not dupes, f"duplicate raw keys found: {dupes}"`，失败输出直接点名重复键；
  测试行为与通过状态不变。（整改来源：
  [reviews-open-issues-fixes-plan.md](../documents/reviews-open-issues-fixes-plan.md)）*
