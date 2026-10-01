# Gitee PR #39 第三轮 AI 评审登记（wiki 生成器 + translate 模块）— 2026-10-01

> 来源：Gitee PR #39 评论 `note_51421951`（conversation_191280605），
> AI 队友（pull_review_bot）2026-10-01 08:02 发起、08:07 完成。
> 评审对象：`tools/pack/wiki.py`、`tools/translate/`（cli/runner）、
> `tools/pack/cli.py` 注册、单测/集成测试、计划文档与 README 更新
> （即本分支 `689ce9e..63e87d3` 区间的全部改动）。

## 一、四维度结论

| 评审规则 | 结论 |
|---|---|
| 功能性与逻辑 | ✅ 通过 |
| 安全性 | ✅ 通过 |
| 性能 | ✅ 通过 |
| 可维护性 | ⚠️ 待优化 |

**总体结论**：⚠️ 无阻断项，发现 1 个改进建议，可优化后合并。风险等级 low。

**风险与影响（评审原文摘要）**：整体逻辑严密且错误处理充分，仅在极端并发修改
源文件的情况下存在极小的崩溃风险；对不可信文档注入和 shell 执行风险均有显式
声明和隔离措施；采用短路读取和单次遍历清理孤儿文件，效率良好。

## 二、改进项（唯一，✅ 已修）

### `_collect_bilingual` 的 TOCTOU（Time-of-check to time-of-use）竞态

- **位置**：`tools/pack/wiki.py`（`_collect_bilingual` 收集阶段 + `run()` 写入分支）
- **问题**：收集阶段以 `en_src.exists()` 判定并赋值 `page.en_source`；
  后续 `run()` 处理该页时直接 `page.en_source.read_bytes()`。若两步之间
  en 源文件被删除/移动，抛出未捕获的 `FileNotFoundError`，整个生成流程崩溃。
- **评审建议修法**：读取 `en_source` 时捕获 `OSError`，降级为缺失页处理
  （落入翻译路径），不崩溃：

```python
if page.en_source is not None:
    try:
        en_path.write_bytes(page.en_source.read_bytes())
    except OSError:
        # Fall through to translation path instead of crashing
        pass
    else:
        manifest.pop(page.zh_target, None)
        kept += 1
        continue
```

- **触发条件**：仅"收集与写入之间双语 en 源被并发删除/移动"的极端场景；
  评审定级为可维护性改进而非缺陷。
- **测试要求**：覆盖"收集后删除 en 源"的场景（构造双语对 → 收集后删 en 源 →
  `run()` 不崩溃且该页按 missing 走翻译路径）。

## 三、处置状态

- ✅ **已修**（2026-10-01，`714183b`）：按评审原文修法实施——`run()` 中
  `en_source.read_bytes()` 包 `try/except OSError`，失败时降级为缺失页处理
  （落入翻译路径），不再崩溃；并按测试要求补回归用例
  `test_en_source_deleted_after_collect_takes_missing_path`
  （`tests/test_pack_wiki.py`，构造双语对 → 收集后删 en 源 → `run()` 不崩溃且
  该页按 missing 走翻译路径）。（整改来源：
  [reviews-open-issues-fixes-plan.md](../documents/reviews-open-issues-fixes-plan.md)）
- 登记轨迹：本文件为唯一登记处（原误登记于
  `.trae/documents/translate-cmd-tool-plan.md` §十一，已按用户要求撤销并移至
  本目录，见 `3b4b889` revert）。
