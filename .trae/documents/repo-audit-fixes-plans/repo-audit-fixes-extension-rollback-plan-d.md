# 子计划 plan-j：扩展 setup 半注册机制化（A13）

> 所属波次：**wave-4**（与 config-options-plan-d 文件不重叠，可并行；主代理执行）。
> 执行者：**主代理**。
> 来源：评审 A13；调研事实 F4（`55e1055` 为 ConPTY 修复与本条无关；现状未机制化；registries 无 `unregister`、Keymap 无 `remove_binding`）。

## 一、输入

- `yate/services/extensions.py:6-9` docstring：setup 抛异常时"已注册内容不保证回收"，要求扩展自行把校验前置——文档约定而非机制；
- `ExtensionAPI`（:282-418）的注册入口：`register_action`（:341）、`register_command`（:398）、`command` 装饰器（:384）、`bind_key`（:345，可同时写 vsc+vim 两个 keymap）；
- `load_file`（:466-529）except 分支只做 `sys.modules.pop`（:523）；
- 覆盖语义（回滚设计的关键约束）：`ActionRegistry.register` / `CommandRegistry.register` 对同名是**替换**（`registries.py:47-49, 80-82`）；`Keymap.add_binding` 对同键是**替换**（`keymaps/base.py:264-272`，stale 条目从 `bindings` 列表移除）——简单删除回滚会在"扩展覆盖内建"场景留下缺口，必须快照-恢复。

## 二、独占文件清单

1. `yate/registries.py`（`ActionRegistry` / `CommandRegistry` 各增 `unregister(name) -> bool`）
2. `yate/keymaps/base.py`（`Keymap` 增 `remove_binding(key_spec) -> bool`，与 `add_binding` 相同的 raw 归一化）
3. `yate/services/extensions.py`（recording 作用域 + `load_file` 回滚 + docstring 更新）
4. `tests/test_registries.py`（unregister 用例）
5. `tests/test_keymap_set.py`（remove_binding 用例）
6. `tests/test_extensions.py`（回滚三态用例）
7. `.trae/rules/architecture-boundaries.md` §四"插件注册"行补一句（机制化登记）

## 三、具体修改

### 3.1 registries.py

- `ActionRegistry.unregister(name) -> bool`：从 `_actions` 弹出，存在返回 True；
- `CommandRegistry.unregister(name) -> bool`：同型。

### 3.2 keymaps/base.py

- `Keymap.remove_binding(key_spec) -> bool`：按 `add_binding` 相同规则归一化 key_spec（`:268`），从 `bindings` 与 `_index` 移除；无此键返回 False。

### 3.3 services/extensions.py

- `ExtensionAPI` 增加注册作用域记录（模块内私有实现，不新增协议/类型层）：
  - `self._scope: list[tuple[str, ...]] | None = None`；每类注册动作在执行**前**快照被覆盖前值：
    - action：`(kind="action", name, previous_get_result)`；
    - command：`(kind="command", name, previous_get_result)`；
    - binding：对每个实际写入的 target keymap 记 `(kind="binding", keymap_name, raw_key, previous_lookup_result)`（`Keymap.lookup` 公开方法取前值，None 表示原无）；
  - 方法：`start_scope() -> None` / `_rollback_scope() -> None`（load_file 同模块调用，下划线私有合规）；
- `load_file`：`setup(self.api)` 调用前 `self.api.start_scope()`；except 分支（:519-525）在 `sys.modules.pop` 后调用 `self.api._rollback_scope()`——回滚语义：前值为 None → unregister/remove_binding；前值非 None → 用快照重新 register/add_binding 恢复；正常加载成功路径 `end_scope()`（清空记录，不回滚）；
- docstring `:6-9` 改写为机制声明："If `setup` raises partway through, every registration
  made through the API is rolled back automatically (previous values restored), so
  callers no longer need to front-load validation."——不变量从文档移进机制；
- 作用域嵌套保护：`start_scope()` 在已有活动作用域时置空旧作用域并 log.warning（load_file 不重入，防御性）。

### 3.4 规则 §四

"插件注册"行（`ActionRegistry` / `CommandRegistry` / `Keymap.add_binding` 经 `ExtensionContext` 暴露）追加：`setup` 失败由 loader 统一回滚（A13 定案）。

## 四、新增测试与验证方案

`tests/test_registries.py` 新增：

1. `test_action_registry_unregister_removes_and_reports_unknown`——arrange: register("a")；act: `unregister("a") is True`、再 `unregister("a") is False`；assert: `get("a") is None`、`names() == []`（正路径 + 未知键边界）。

`tests/test_keymap_set.py` 新增：

2. `test_keymap_remove_binding_roundtrip_and_missing_key`——arrange: `Keymap()` 子类实例 `add_binding("<ctrl-j>", "some.action")`；act: `remove_binding("<ctrl-j>")`；assert: `lookup(...)` 归一化键为 None、返回 True；再 remove 返回 False（未归一化别名键传入也按 raw 匹配）。

`tests/test_extensions.py` 新增（回滚三态）：

3. `test_failed_setup_rolls_back_new_registrations`——arrange: 写临时扩展文件，setup 先 `api.register_action("x", ...)`、`api.command("y")(fn)`、`api.bind_key("<ctrl-u>", ...)`，然后 `raise RuntimeError`；act: `loader.load_file(path)`；assert: `record.error` 非 None；`actions.get("x") is None`、`commands.get("y") is None`、两个 keymap 的 `lookup` 均为 None；`teardown_all()` 不调用该扩展（teardown 未捕获）。
4. `test_failed_setup_restores_overridden_builtin_registration`——arrange: 先经同一 API 注册 action "dup"（充当"内建"），再加载第二个扩展 setup 内重新 `register_action("dup", ...)` 后 raise；act: load_file；assert: `actions.get("dup").func` 恢复为第一个函数对象（快照-恢复语义，覆盖场景不留缺口）。
5. `test_successful_setup_keeps_registrations`——arrange: setup 注册后正常返回；act: load_file；assert: 注册全部存活且 record.error is None（正常流，防回滚误伤）。

验证命令（退出码 0）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_extensions.py tests/test_registries.py tests/test_keymap_set.py tests/test_extension_examples.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
```

手工验证：`yate/extensions/uppercase.py.example` 语义未变（bundled 扩展 setup 全部成功的常规路径零行为差异）。

## 五、风险与回滚

- 风险 R3（主计划）：覆盖恢复语义错误 → 用例 4 钉死快照-恢复；嵌套作用域防御分支；recording 只在 `load_file` 调用窗口活动，对 `teardown_all` / 运行期注册零影响。
- 回滚：revert 后 docstring 恢复"文档约定"声明（回滚即回到现状，无中间态）。
