# SP2 — editor_syntax 语法（N2 N3 N4）

> 波次一 · 规模 M · [P2 原文](../P2_nice_to_have_plan.md)为唯一规范来源。

## 独占文件清单

**产品（任务书逐文件显式授权）：**
- `yate/editor_syntax/regex_backend.py`（N2）
- `yate/editor_syntax/ts_backend/languages.py`（N3）
- `yate/editor_syntax/ts_backend/backend.py`（N4，纯注释）

**测试：** `tests/test_highlight.py`、`tests/test_syntax_engine.py`、`tests/test_ts_backend.py`（仅新增）

不许动其它任何文件；范围外发现上报主代理。

## 第 0 步：现状复核

逐条核对 P2 原文锚点（N2: config tokenizer 各 `finditer` 独立发射致重叠 token；
N3: languages.py `getattr(dll, symbol)` 裸 `AttributeError`；N4: backend.py `_to_char` 注释缺失）。
py-tree-sitter 为可选依赖——N3/N4 相关测试须兼容 ts 后端缺席时的 skip 形态（参照既有用例）。

## 条目执行

### N2 — config tokenizer 消除重叠 token

1. **输入**：P2 原文 N2 行（按 start 排序后重叠取先到者，或合并单次交替扫描——实施时选改动面小者）。
2. **步骤**：先读 `_tokenize_config_line` 全函数，确认各 token 类别的优先级语义
   （字符串内的数字/布尔词应让位于字符串 token）；重构发射逻辑为区间不重叠。
3. **输出**：`"true1"`、字符串内数字等场景不再双着色。
4. **验收**：新增两条用例（`true1` 布尔词不命中词内；字符串内数字只按字符串着色）；
   既有 config 高亮用例全绿。**注意**：P1 波次二刚改过该文件的布尔词正则（`_CONFIG_BOOL_RE`
   模块级预编译），以当前代码为基准，不得回退该优化。

### N3 — 缺符号报错带上下文

1. **输入**：P2 原文 N3 行（`getattr` 包 try，`raise RuntimeError(f"{library_path} lacks entry point {symbol!r} ...") from e`；`_FAILED` 缓存防重复）。
2. **步骤**：定位 `getattr(dll, symbol)` 调用点；包 `try/except AttributeError` 后带路径与符号名重抛；
   确认失败态仍进 `_FAILED` 缓存（不改变缓存语义）。
3. **输出**：缺符号错误消息含库路径与符号名，可定位。
4. **验收**：monkeypatch 假 dll 缺符号 → `pytest.raises(RuntimeError, match=...)` 断言消息含两者；
   既有 languages 用例全绿（含依赖缺席 skip）。

### N4 — `_to_char` 字节偏移边界注释

1. **输入**：P2 原文 N4 行（说明 UTF-8 多字节中间偏移经 `errors="ignore"` 丢弃后续字节、映射到字符首列）。
2. **步骤**：读 `_to_char` 实现，注释与实际行为一致；不改代码。
3. **验收**：纯注释；pyright + 既有用例全绿。

## 收尾清单

- [ ] `.venv\Scripts\python.exe -m pyright yate/editor_syntax/regex_backend.py yate/editor_syntax/ts_backend/languages.py yate/editor_syntax/ts_backend/backend.py tests/test_highlight.py tests/test_syntax_engine.py tests/test_ts_backend.py` → 0 诊断
- [ ] `.venv\Scripts\python.exe -m pytest tests/test_highlight.py tests/test_syntax_engine.py tests/test_ts_backend.py -q` → exit 0
- [ ] 报告：改动清单 + 实跑命令与结果 + 校准记录

## 校准记录

（实施时回填）
