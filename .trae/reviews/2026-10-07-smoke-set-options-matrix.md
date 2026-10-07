# 冒烟存量失败修复：`set_options_matrix / keymap_warned` — 2026-10-07

> 发现途径：issue IKJUWP（回调别名化）分支 `ref/callable-aliases` 的独立审核环节，
> `code-review-expert` 跑全量冒烟时命中；评审在 `master` 原样导出上复现同一失败，
> 确认**与本分支无关**，属存量缺陷（自 `8b529d4` 起潜伏）。
> 关联方案：[callable-aliases-plan.md](../documents/callable-aliases-plan.md) §九门禁表。

## 一、现象

`python -m tools.smoke_test run --skip-slow` 全量冒烟：101/102 scenarios、
1235/1236 checks，唯一失败项

```
set_options_matrix / keymap_warned   expected True / actual False
```

单场景复跑同样失败（与并发无关，排除 timing 类偶发）。

## 二、根因（证据链）

失败断言位于 `tools/smoke_test/scenarios/view.py:113`（修复前）：

```python
await run_command(pilot, "set keymap=nope")
checks.append(Check("keymap_warned", True, "unknown keymap" in message_text(app)))
```

`:set keymap=nope` 的实际提示语由**选项表**决定（`yate/commands.py:268-270`）：

```python
parsed = spec.parse(value)
if parsed is None:
    editor.message(spec.invalid_message, kind="warn")
```

而该选项的 `invalid_message` 是 `yate/config.py:264` 的 `"keymap must be vsc or vim"`
——`_parse_keymap` 对未注册的名字返回 `None`，走的是"值非法"分支，
**不是** `yate/editor.py:750` 那条 `unknown keymap: ... (vsc|vim)` 的提示
（后者属于 `:keymap <名字>` 命令路径，至今仍在使用，两条路径的文案本就不同）。

时间线取证：

```
git log -S "unknown keymap"          -- yate tools tests → 42d9b12 / 9fa5ac8 / 5c22c8d / ef1d964（断言与旧文案同期）
git log -S "keymap must be vsc or vim" -- yate tools tests → 8b529d4（表驱动 :set，A8/A9）
```

`8b529d4 refactor(config): split the loader into yaterc.py and table-drive :set`
把解析与提示语收进 `SET_OPTION_SPECS`，文案随之改变，而冒烟断言仍钉着旧字符串，
从此恒定失败。`tools/smoke_test/smoke_baselines/set_options_matrix.json` 里
`keymap_warned` 记录为 `ok: true`——那是 A8 之前录下的基线，基线只作对照、不参与判定，
所以失败一直被"基线说是好的"掩盖。

结论：**产品行为正确，测试断言过期**。修复方向是修断言，不是把提示语改回旧文案
（表驱动文案是刻意设计，且与其它选项的 `invalid_message` 保持一致）。

## 三、修复

`tools/smoke_test/scenarios/view.py`——断言改为**跟随选项表**，不再钉死字面量：

```python
from yate.commands import SET_OPTION_INDEX
...
        # The reject wording lives in the option table (A8), so read it from
        # there instead of pinning a literal that a table edit would outdate.
        keymap_reject = SET_OPTION_INDEX["keymap"].invalid_message
        checks.append(Check("keymap_warned", True,
                            keymap_reject in message_text(app)))
```

这样断言校验的仍是"非法 keymap 被拒绝**且**用户看到了表里约定的提示"这一契约，
但下次改文案不会再让冒烟恒失败。基线文件无需改动：label 与 expected 均未变，
修复后实际值回到 `true`，与基线一致。

排除连带问题：同一场景的 `option_warned`（`"unknown option"`）对应
`yate/commands.py:266` 未被 A8 触碰，全量冒烟中它一直通过，保持原样。

## 四、验证（主代理亲自跑，worktree 内 `.venv`）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m tools.smoke_test run --scenario set_options_matrix --no-color` | 0 | **16/16 checks**，含 `keymap_warned = True` |
| `python -m tools.smoke_test run --skip-slow --no-color` | 0 | **102/102 scenarios，1236/1236 checks**（修复前 101/102） |
| `python -m pyright yate/ tests/ tools/` | 0 | `0 errors` |
| `python -m pytest tests/ -q` | 0 | 全绿（纯测试代码改动，产品源码未变） |

## 五、举一反三

同批排查了其余可能同类腐化的点，结论是无需改动：

- 全仓仅此一处断言钉死了 `:set` 的选项表文案（`grep "unknown keymap"` 只命中
  `yate/editor.py:750` 的另一条命令路径与本场景）；
- 其余冒烟断言命中的文案（`unknown option`、`keymap`、`theme`、`terminal_height` 等）
  均来自未被 A8/A9 改写的代码路径；
- 建议的后续动作（未做，不在本次范围）：冒烟基线若改为"参与判定"而非纯对照，
  这类过期断言会在录制时就暴露；改动面涉及基线比较逻辑，需单独立项。