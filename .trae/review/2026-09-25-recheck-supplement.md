# yate Code Review — 复审补充 — 2026-09-25

## 复审补充 — 2026-09-25

> 来源：外部审查工具报告的 2 个改进项，指向 `editor_core/document.py` 与
> `editor_view/editor.py`；主代理现场读码核实：**① 不成立（所述代码不存在，误报）**，
> **② 成立且未修**。均登记于此，**均未修**。复核基准：2026-09-25 当前代码
> （分支 `issues/nice-to-have-enh`）。

- ⛔ **EOL 写回对 buffer 内嵌 `\r` 的行为需确认（不成立 / 误报，功能性）** — 报告位置
  [`document.py` `save()`](../../yate/editor_core/document.py)
  **报告描述**：保存时 `if self.eol != "\n": text = text.replace("\n", self.eol)`，
  若编辑期间粘贴或插入的内容含字面 `\r`，CRLF 文件会出现 `\r\r\n` 等异常序列。
  **核实结论：前提不成立**，四条依据：

  1. 全仓 `yate/` 检索 `\beol\b`（含 `fileformat`）**0 命中**——`Document` 没有 `eol`
     属性，代码库中**不存在任何 EOL 写回（LF→CRLF）转换**；
  2. [`save()` 第 168 行](../../yate/editor_core/document.py#L168) 取 `self.buffer.get_text()`
     后直接 `encode` 写盘，**无任何换行替换**，因此不可能在既有 `\r` 之上再叠加出 `\r\r\n`；
  3. 唯一的换行归一化在 [`Document.open()` 第 67 行](../../yate/editor_core/document.py#L67)，
     而它做的**正是建议中的防御性归一化**：`text.replace("\r\n", "\n").replace("\r", "\n")`
     ——即"读取时收敛为 LF、保存统一写 LF"（`open()` 上方注释已明确该契约）；
  4. 建议的修复代码若加入 `save()`，反而是给一个不存在的路径加转换。

  **处置**：按误报归档。保留记录以备将来真引入 EOL 选项时可复查。
  **衍生观察（未成条，暂无可达路径）**：`TextBuffer.insert_text`
  ([buffer.py:309](../../yate/editor_core/buffer.py#L309)) 不处理 CR；但当前编辑器**未接入系统剪贴板粘贴**
  （`paste` action 走内部寄存器，见 [actions.py:117](../../yate/actions.py#L117)；`Paste` 事件仅终端面板消费，
  [terminal.py:224](../../yate/editor_view/terminal.py#L224)），故字面 `\r` 无入口进缓冲区。
  **将来若增加系统剪贴板粘贴入口，必须在该入口做 CR 归一化**，否则会写出含裸 CR 的文件。

- [ ] **`HighlightProbe.doc` 建议使用精确类型（Low，可维护性）** —
  [`editor.py:62`](../../yate/editor_view/editor.py#L62)
  ```python
  @dataclass(frozen=True)
  class HighlightProbe:
      doc: object     # ← 宽泛类型，削弱探针作为公开调试接口的静态检查价值
  ```
  **核实：成立。** 该文件第 19 行已 `from yate.editor_core.document import Document`，
  可直接收紧为 `doc: Document`。作为上一轮 S28（测试深访私有 highlight 属性）的产物，
  探针是测试唯一允许碰的接口，类型精度直接决定 guard 的有效性。
  **修复注意事项（核实所得）**：
  - 同文件第 144 行初值 `self._hl_doc: object = None` 同样需改，但它是 **`None` 初值**，
    直接写 `Document` 会被 pyright strict 判错，应改 `Optional[Document] = None`；
    而 `HighlightProbe.doc` 字段由 `highlight_probe()` 构造时传入真值，可写 `Document` 不必 Optional；
  - 受影响守卫见 [test_app_textual.py:338-343](../../tests/test_app_textual.py#L338-L343)
    （`highlight_probe().doc is editor.doc`）——为身份比较，收紧类型不影响通过。
