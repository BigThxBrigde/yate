# SP5 — keymaps 与注册表（N20 N21 N23 N25）

> 波次二 · 规模 M · [P2 原文](../P2_nice_to_have_plan.md)为唯一规范来源。

## 独占文件清单

**产品（任务书逐文件显式授权）：**
- `yate/keymaps/vim.py`（N20 N21）
- `yate/keymaps/base.py`（N23 N25）

**测试：** `tests/test_vim_keymap.py`、`tests/test_registries.py`（仅新增）

**不许动**：`tests/test_app_textual.py`（SP6 独占）、`yate/registries.py`（N25 只改 base.py 的
callable 别名；已核实无跨文件引用——见下）、其它任何文件。

## 第 0 步：现状复核

逐条核对 P2 原文锚点（N20: visual `gg` 死代码；N21: `if key == "o": pass`；N23: `add_binding`
覆盖 `_index` 后旧 binding 残留；N25: base.py:160 `Action = Callable[...]` 与 registries.py 的
dataclass 同名）。**已核实的事实**：`keymaps/__init__.py` 不 re-export `Action` 别名，`docs/`
全文零引用——N25 波及面收敛在 base.py 单文件。实施中若发现任何外部引用，停下上报。

## 条目执行

### N20 — visual 模式 `gg` 死代码处置

1. **输入**：P2 原文 N20 行（`pending` 恒空且 `"g"` ∈ motion 表，第二分支不可达；删死分支或修正条件使其可达）。
2. **步骤**：读 visual 模式 `gg` 分支现状；默认**删除死分支**（最小改动，真实 vim 中 visual gg
   支持属新功能，不在 P2 范围）；若倾向实现 visual gg 跳转，先上报主代理拍板，不得擅自扩功能。
3. **输出**：死分支删除，visual 模式按键行为不变（`gg` 在 visual 下仍为不可达/无操作，按删后实际语义固化）。
4. **验收**：既有 vim 用例全绿；新增固化用例记录删后行为（visual 下 `gg` 的实际表现）。

### N21 — `if key == "o": pass` 死代码删除

1. **输入**：P2 原文 N21 行。
2. **验收**：删除；既有 vim 用例全绿。

### N23 — `add_binding` 覆盖后旧 binding 残留

1. **输入**：P2 原文 N23 行（覆盖时从 `bindings` 列表移除同 raw key 旧条目）。
2. **步骤**：读 `add_binding` 对 `_index` 与 `bindings` 列表的双写现状；覆盖路径同步清理列表旧条目。
3. **输出**：同 key 重复 `add_binding` 后帮助（modals 遍历 `bindings`）只展示一条。
4. **验收**：`test_vim_keymap.py` 新增 **Keymap 层**守卫——同 raw key 两次 `add_binding`
   后断言 `bindings` 列表该 key 仅一条。**不做 app 级断言**（modals 渲染测试在 SP6 独占文件里）；
   若认为必须 app 级验证，上报主代理协调，不得越界改文件。

### N25 — `Action` 别名改名 `ActionFunc`

1. **输入**：P2 原文 N25 行（callable 别名改 `ActionFunc`，与 registries 的 `CommandFunc` 命名对齐）。
2. **步骤**：base.py 内 `Action = Callable[...]` → `ActionFunc = Callable[...]`；更新该文件内
   全部使用点；pyright 全绿即确认无漏网。
3. **输出**：两处同名消除；`registries.py` 的 dataclass `Action` 不动。
4. **验收**：pyright 0 诊断（含全仓复核由主代理收尾）；`test_registries.py` 既有用例全绿；
   报告注明「已核实 docs/ 与 keymaps/__init__ 无引用，无需文档同步」。

## 收尾清单

- [ ] `.venv\Scripts\python.exe -m pyright yate/keymaps/vim.py yate/keymaps/base.py tests/test_vim_keymap.py tests/test_registries.py` → 0 诊断
- [ ] `.venv\Scripts\python.exe -m pytest tests/test_vim_keymap.py tests/test_registries.py -q` → exit 0
- [ ] 报告：改动清单 + 实跑命令与结果 + N20 处置选择（删除/实现）+ 校准记录

## 校准记录

（实施时回填）
