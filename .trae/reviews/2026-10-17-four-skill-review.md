# 2026-10-17 分支 `enh/full-repo-audit` 四技能联合审核（第三轮）

- 分支：`enh/full-repo-audit`（worktree `../yate-full-repo-audit`，HEAD `58116ba`）
- 范围：`git diff master...HEAD` 全部改动（28 文件，+2717/−205；其中代码 10 文件
  +357/−181，其余为计划/规则/评审文档）
- 形态：**只读事实文档**——只记录发现与核对结论，不含修复排期（doc-conventions §二.1）
- 审核链：按用户指令依次以 `TRAE-code-review` / `TRAE-security-review` /
  `python-code-review` / `pr-review` 四个技能独立评审同一 diff，主代理汇总去重
- 交叉引用：前两轮评审与修复
  [`2026-10-17-full-repo-audit-code-review.md`](2026-10-17-full-repo-audit-code-review.md)、
  [`../documents/full-repo-audit-code-review-fixes-plan.md`](../documents/full-repo-audit-code-review-fixes-plan.md)
  （C-1…C-6 已全部落地）；修复方案
  [`../documents/full-repo-audit-four-review-fixes-plan.md`](../documents/full-repo-audit-four-review-fixes-plan.md)

## 一、四技能逐项结论

| # | 技能 | 结论 | 发现（去重前） |
|---|---|---|---|
| 1 | TRAE-code-review | REQUEST_CHANGES | 1 MAJOR（FS-1）+ 2 验证者交叉确认 |
| 2 | TRAE-security-review | 无可利用问题（✅ clean） | 0——本 diff 无新增输入入口/汇点；emulator 钳制为攻击面收窄 |
| 3 | python-code-review | MINOR ISSUES | 1 WARNING（FS-1 同项）+ 零 SUGGESTION |
| 4 | pr-review | 见 §三 门禁与裁定 | 1 MAJOR（FS-1 同项）；架构边界自检六维零违规 |

**去重后净发现：1 条代码缺陷（FS-1，MAJOR）+ 1 条文档措辞失准（FS-2，MINOR）。**

## 二、逐条发现

### FS-1 [MAJOR] `key_name` 解码 kitty CSI-u 修饰位未减基偏移，round-trip 不自洽

- 位置：`yate/keymaps/keys.py:172-180`（本分支自 `base.py` 整段搬迁的新 L0 文件）
- 证据（运行时探针，2026-10-17 主代理实测）：
  - `parse_key("<ctrl-1>")` → `'\x1b[49;5u'`（kitty 约定 `mod = 1 + bitmask`，
    shift=1 / alt=2 / ctrl=4）
  - `key_name('\x1b[49;5u')` → `'<shift-ctrl-1>'`（应为 `<ctrl-1>`）
  - `key_name('\x1b[49;6u')` → `'<alt-ctrl-1>'`（应为 `<shift-ctrl-1>`）
- 根因：`parse_key` 发码按 kitty 协议（修饰字段 = 1 + 位掩码），`key_name` 解码
  （`m = re.fullmatch(r"\x1b\[(\d+);(\d+)u", key)` 后 `mod & 1` / `mod & 2` /
  `mod & 4`）把修饰字段当**裸位掩码**，基偏移 1 被误判为 shift 位。
- 可达性：默认键表 [`yate/keymaps/vsc.py:113`](../../yate/keymaps/vsc.py) 的
  `<ctrl-1> → focus_editor` 绑定经 `KeyBinding.key_label`（`keymaps/base.py:49-51`）
  进帮助覆盖层，标签显示为 `<shift-ctrl-1>`；扩展/用户绑定同理。
- 溯源：缺陷随 `c525d70`（keymaps 拆分）整段搬迁自 `base.py`，非本轮新写；但
  keys.py 为本 diff 新增文件，按「diff 引入面」口径计为本轮发现。
- 交叉验证：TRAE-code-review 技能 §5.5 双验证子代理并行确认存在性与严重度
  （2/2，高置信），与主代理探针三方一致。

### FS-2 [MINOR] 修复计划文档对 C-4 可区分性的表述失准（文档措辞，非代码）

- 位置：[`../documents/full-repo-audit-code-review-fixes-plan.md`](../documents/full-repo-audit-code-review-fixes-plan.md)
  §六 Wave B：「负向可区分旧实现，旧实现得 `4`」
- 实测推演：窄区域（DECSTBM 1;2）下旧钳制 `min(count, rows)` 得 4 次迭代、新钳制
  得 2 次，但**两种实现下 `emu.max_scroll()` 均为 2**（区域第 3/4 次滚动为幂等空转，
  不再产生 scrollback）——测试的区分度来自工作量上界，而非该断言值。
- 影响：计划文档的执行记录陈述与实测不符（用例本身仍有效，锚定语义正确）。

## 二·补、FS-3（验收追加上报，2026-10-17 实施期发现）

四技能评审均未跑冒烟；Wave A 验收组合追跑冒烟门禁时暴露：

### FS-3 [MAJOR] 冒烟替换场景未同步 per-match confirm loop 契约（master 既有）

- 现象：`replace_single_all` FAIL(3) / `replace_all_clamp` FAIL(4)——第二次 enter 后
  零替换、matches 不清零、`modified` False。
- 定性（三重实证）：stash A/B 对照失败逐字一致 + master 主检出复跑同样失败 →
  **非本分支引入**；根因 master `ad237e5`（2026-10-16）将 F4 替换改为逐匹配确认循环
  （第二次 enter 后进入 `replace_confirm`：y 逐个 / a 全替 / q 退），冒烟场景仍断言
  旧的「第二次 enter 即全替」。
- 处置：按全仓审计分支章程在本分支修复（场景补 `replace_confirm` 锚点 + 按 `a`
  全替兜底键），见修复方案 Wave A2。

## 三、pr-review 门禁实测（主代理亲跑，worktree 沙箱）

| 门禁 | 结果 | 退出码 |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | 0 errors / 0 warnings / 0 informations | 0 |
| `python -m pytest tests/test_architecture.py -q` | 32 passed | 0 |
| `python -m pytest tests/ -q` | 2485 passed, 9 skipped（进度点逐字符统计，零 F/E） | 0 |
| `python -m pytest tests/ -q --cov --cov-fail-under=75` | TOTAL 91%（`coverage report`，与分支前值 91.94% 同水位） | 0（≥75） |

架构边界自检（pr-review 维度 5）：本 diff 无 R1–R14 违规信号；无新增
`Protocol` / `TYPE_CHECKING` / `App[Any]` / `# type: ignore`；命名无
`*Feature` / `*Host` / `*Ops` / `*Delegate` / `*Controller`；`keys.py` 为合规
L0 叶（仅 `import re`）；`base.py` 再导出形态与内部使用一致
（`KEY_ALIASES` / `SPECIAL_KEYS` 纯再导出用显式 `as`，`key_name` / `parse_key`
在 `base.py:51,112` 有内部使用故为普通导入）。

## 四、处置状态

- FS-1 / FS-2 的修复排期见
  [`../documents/full-repo-audit-four-review-fixes-plan.md`](../documents/full-repo-audit-four-review-fixes-plan.md)
  （互链）；
- 复审（第 6 步 pr-review）结论另起记录。

## 五、复现口径（只读）

```powershell
git -C ../yate-full-repo-audit --no-pager diff master...HEAD --stat   # 28 文件 / +2717-205
.venv\Scripts\python.exe -c "from yate.keymaps.keys import parse_key, key_name; print(key_name(parse_key('<ctrl-1>')))"  # <shift-ctrl-1>（应为 <ctrl-1>）
```

探针为一次性验证，不入库（misc-rules §二）。
