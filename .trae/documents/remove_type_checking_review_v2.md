| 评审规则   | 评审内容                            | 评审结论   | 完成时间                |
| ------ | ------------------------------- | ------ | ------------------- |
| 功能性与逻辑 | 代码是否按预期执行？有无逻辑错误或未处理的边缘情况？      | ❌ 未通过  | 2026-09-18 14:48:25 |
| 安全性    | 是否存在 SQL 注入、XSS、命令注入、敏感信息泄露等风险？ | ✅ 通过   | 2026-09-18 14:48:25 |
| 性能     | 是否有明显的性能瓶颈（如循环嵌套过深、冗余查询、内存泄漏）？  | ✅ 通过   | 2026-09-18 14:48:25 |
| 可维护性   | 代码是否清晰易读？注释是否充分？命名是否合理？         | ⚠️ 待优化 | 2026-09-18 14:48:25 |

## 🤖 AI 队友审查结果

### 📊 审查结论

⛔ 发现 1 个阻断项，3 个改进项。请修改后再合并。

### 风险与影响

- **风险等级**：medium
- **潜在影响**：本次 PR 的核心价值在于通过 `AppProtocol` 彻底解耦上下层模块，消除循环依赖，提升代码架构的清晰度和可测试性。然而，`yate/app_features/completion.py` 中的 `accept()` 方法存在严重的逻辑错误——`row != r0 or row != r1` 条件会使所有跨行（multi-line）补全被无条件拒绝。这将直接影响用户在使用多行文本补全时的体验，属于功能性阻断问题。此外，`AppProtocol` 中广泛使用 `Any` 类型降低了静态类型检查的有效性，长期来看会影响代码质量和 IDE 体验。

---

### 🔍 改动检查

本 Pull Request 涉及 23 个文件的大规模重构，主要目标是移除所有 `TYPE_CHECKING` 块，引入 `yate/interfaces.py` 中的 `AppProtocol` 作为依赖倒置层，同时提取 `yate/editor_view/pane_types.py` 作为纯数据模型以打破循环依赖。以下是对关键变更的分析：

- **新增文件**：`yate/interfaces.py` 定义了 `AppProtocol`（Protocol-based 抽象层），`yate/editor_view/pane_types.py` 包含面板树数据结构
- **核心模式变更**：几乎所有文件的函数签名从 `app: "YateApp"`（字符串前向引用）变为 `app: AppProtocol`
- **Import 变化**：移除了约 18 个文件中的 `from typing import TYPE_CHECKING` 及对应的 `if TYPE_CHECKING:` 块，改为直接导入 `AppProtocol`
- **类型注解简化**：由于已有 `from __future__ import annotations`（PEP 563），所有注解在运行时都延迟求值为字符串，不再需要 `TYPE_CHECKING` 来避免循环导入
- **功能增强**：`yate/app_features/completion.py` 的重写引入了更完善的补全陈旧性检测机制

---

### 🚫 阻断项

1. **🔴 `accept()` 中条件 `row != r0 or row != r1` 导致跨行补全被错误拒绝** (功能性与逻辑) : `yate/app_features/completion.py`
   - **问题描述**：在 `CompletionController.accept()` 方法中存在逻辑错误：条件 `row != r0 or row != r1` 在跨行补全范围（`r0 != r1`）时始终为 `True`，导致所有跨行补全被无条件拒绝。

```
def accept(self) -> None:
    ...
    if item.has_range():
        r0 = item.range_start_row or 0
        c0 = item.range_start_col or 0
        r1 = item.range_end_row or 0
        c1 = item.range_end_col or 0
        # Cursor left the row(s) the completion was for — discard.
        if row != r0 or row != r1:    # ← 问题行
            return
```

当 `r0 != r1` 时，`row` 不可能同时等于 `r0` 和 `r1`，因此该条件永远为真。

- **修正建议**：将条件改为检查光标是否离开补全范围的行边界，仅当光标完全超出 `[r0, r1]` 区间时才丢弃补全。

```
def accept(self) -> None:
    ...
    if item.has_range():
        r0 = item.range_start_row or 0
        c0 = item.range_start_col or 0
        r1 = item.range_end_row or 0
        c1 = item.range_end_col or 0
        # Only discard if cursor is outside the vertical range of the completion.
        if row < r0 or row > r1:
            return
```

或者等价的写法：`if not (r0 <= row <= r1):`

### ⚠️ 改进项

1. **🟡 `AppProtocol` 中过多使用 `Any` 削弱类型安全性** (可维护性) : `yate/interfaces.py`
   - **问题描述**：`AppProtocol` 中大量字段使用 `Any` 类型而非真实的类型注解，使得类型检查器和 IDE 失去静态分析能力。

```
class AppProtocol(Protocol):
    workspace: Any              # yate.services.workspace.Workspace
    keymaps: dict[str, Any]     # dict[str, Keymap]
    active_keymap: Any           # Keymap
    config: Any                  # yate.config.YateConfig
    actions: Any                 # yate.actions.ActionRegistry
    commands: Any                # yate.app_features.commands.CommandRegistry
    extension_loader: Any        # yate.services.extensions.ExtensionLoader
    screen_stack: list[Any]
    screen: Any
    ...
    run_shell_command(...) -> Any
```

由于模块已启用 `from __future__ import annotations`，可以使用字符串前向引用来保留类型信息而不引起循环导入。

- **修正建议**：对于不会导致实际运行时导入冲突的类型，建议使用字符串前向引用替代 `Any`：

```
class AppProtocol(Protocol):
    workspace: 'Workspace'       # 字符串前向引用
    keymaps: dict[str, 'Keymap']
    active_keymap: 'Keymap'
    config: 'YateConfig'
    actions: 'ActionRegistry'
    commands: 'CommandRegistry'
    extension_loader: 'ExtensionLoader'
    screen_stack: list['Screen']
    screen: 'Screen'
    ...
    run_shell_command(...) -> object
```

这样既保留了类型安全，又避免了循环导入问题。

2. **🟢 `Leaf.states` 的 `default_factory` 可简化** (可维护性) : `yate/editor_view/pane_types.py`
   - **问题描述**：`Leaf.states` 的 `default_factory` 使用了不必要的 lambda 包装。

```
states: dict[int, ViewState] = field(
    default_factory=lambda: dict[int, ViewState]()
)
```

虽然代码是正确的（每次实例化会产生独立的字典），但写法不够简洁。

- **修正建议**：将 lambda 包装简化为直接使用 `dict` 类型引用，更加 Pythonic：

```
states: dict[int, ViewState] = field(default_factory=dict)
```

行为完全等价，代码更简洁。

3. **🟢 `remove_node` 原地修改可能导致副作用** (可维护性) : `yate/editor_view/pane_types.py`
   - **问题描述**：`remove_node` 函数原地修改传入节点的 `children` 和 `sizes` 属性，而函数的返回值为新的 `Node` 结构，存在语义不一致。

```
def remove_node(node: Node, target: Leaf) -> Optional[Node]:
    ...
    node.children = new_children
    node.sizes = _normalized(node.sizes[: len(new_children)])
    return node
```

如果有其他代码持有同一 `Split` 实例的引用，可能会被意外影响。

- **修正建议**：如果意图是返回新树而非就地修改，应在修改前先拷贝 `node`；或在文档中明确说明此函数会原地修改传入的节点。推荐方案：

```
def remove_node(node: Node, target: Leaf) -> Optional[Node]:
    if isinstance(node, Leaf):
        return None if node is target else node
    new_children: list[Node] = []
    for child in node.children:
        result = remove_node(child, target)
        if result is None:
            continue
        new_children.append(result)
    if len(new_children) == 1:
        return new_children[0]
    # Copy to avoid mutating the original Split
    node_copy = Split(axis=node.axis, children=new_children, sizes=_normalized(node.sizes[:len(new_children)]))
    return node_copy
```

同时在 docstring 中注明行为。
