# SP4 — 键映射与补全语义（S30 + S31 + S35 + S38）

> 来源：[P1 批次六](../P1_suggestions_plan.md)。统一门禁见 [README §五](README.md)。

## 条目

| 条目 | 证据锚点 | 内容 | 规模 |
|---|---|---|---|
| S30 | [completion.py:128、:202-219](../../../../yate/completion.py) | Esc 关闭弹窗后，在途 worker 落地仍把它重新显示 | M |
| S31 | [vim.py:477-490](../../../../yate/keymaps/vim.py) | vim 操作符删除（`dw`/`d$`）不写寄存器 | S |
| S35 | [vim.py:303-321](../../../../yate/keymaps/vim.py) | `dg`/`yg` 空 motion 仍报 "deleted"/"yanked" | S |
| S38 | [registry.py:19-21](../../../../yate/keymaps/registry.py) | `KeymapSet` 空字典抛裸 `StopIteration` | S |

## 独占文件清单（只许改这些）

- `yate/completion.py`
- `yate/keymaps/vim.py`
- `yate/keymaps/registry.py`
- `tests/test_completion_popup.py`、`tests/test_vim_keymap.py`、`tests/test_registries.py`（新增用例）

## 实施步骤

1. **第 0 步 复核**：四条锚点逐一确认（重点 S30：`popup.close()` 是否仍不取消在途请求、
   `_stale()` 是否仍不检查「用户已显式关闭」）。
2. **S30**：关闭时记录「用户已忽略」标记（或递增 generation / 取消在途 worker），
   `_worker` 与 `_stale()` 一并检查；用户再次主动触发（`Ctrl+Space` 或前缀变化）时清除。
   **注意**：`after_editor_key` 的 `schedule()` 属主动输入路径的 guarded re-query，
   **保留**，不要误伤。验收：pilot 用例——弹窗打开 → Esc → 推进防抖与 worker 落地 →
   `is_open` 保持 False；再按 `Ctrl+Space` → 弹窗恢复。
3. **S31**：与 visual 路径（vim.py:217-219）一致，捕获 `buf.delete_selection()` 返回值
   写入 `buf.register`。验收：`yy` → 移动 → `dw` → `p` 粘出被删文本；`dw` → `p` 粘出被删词。
4. **S35**：操作符等待态排除 `"g"`（`gg` 是位置跳转不是操作符范围）。
   验收：`dg` / `yg` 后无 deleted/yanked 消息、缓冲不变。
5. **S38**：`next(...)` 改为显式 `raise ValueError("no keymaps registered")`。
   验收：空注册表调用 `pytest.raises(ValueError)`。
6. **子代理门禁**：
   ```Shell
   .venv\Scripts\python.exe -m pyright yate/completion.py yate/keymaps tests/test_completion_popup.py tests/test_vim_keymap.py tests/test_registries.py
   .venv\Scripts\python.exe -m pytest tests/test_completion_popup.py tests/test_vim_keymap.py tests/test_registries.py -q
   ```

## 注意

- S30 的状态标记放在 `completion.py`（L3 流程模块）内部，不改 editor.py 的弹窗按键分支
  （那是 SP3 的文件），不新增跨层依赖（R11）。
