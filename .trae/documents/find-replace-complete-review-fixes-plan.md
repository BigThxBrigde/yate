# find-replace-complete-review-fixes-plan

> 来源记录：[`.trae/reviews/2026-10-16-find-replace.md`](../reviews/2026-10-16-find-replace.md)
> （第一轮 PR 预审，2 MAJOR；第三轮 code-review-expert，3 MAJOR + 4 MINOR）。
> 修复范围：磁盘替换路径与回归测试（§二-§四）；行视图一致性 / reveal 钳制 /
> 滚动跟随等（§五）。

## 一、目标与非目标

### 目标

1. `_replace_on_disk` 行保真：只按 `\n` 切行（与 `TextBuffer` /
   `SearchEngine` 同语义），字节级往返（CRLF / LF / CR 文件除替换命中
   附近外逐字节不变），`\u2028` 等合法分隔符不再被改写。
2. 落盘原子化：对齐 `Document.save` 的临时文件 + `os.replace` +
   `copystat` 惯例，mid-write 崩溃不破坏原文件。

### 非目标

- 两条 MINOR（命中文件二次读盘、空替换守卫）缓办，登记 follow-up；
- 不改打开 buffer 的内存替换路径（`_replace_open` 行为正确）。

## 二、备选方案与否决理由

| # | 议题 | 选定 | 否决 |
|---|---|---|---|
| F1 | 行保真实现 | `text.split("\n")` + `"\n".join(...).encode()` + `write_bytes` 语义（经临时文件二进制写） | `splitlines` + `write_text(newline="")`：`splitlines` 本身就丢分隔符信息（`\u2028` 仍被拆行），必须换切分算子；`newline=""` 只解决翻译，不解决切分 |
| F2 | 原子写实现 | 就地复刻 `Document.save` 形态（`tempfile.mkstemp(dir=parent)` + `os.fdopen` + `copystat` + `os.replace`） | 抽公共 helper 复用 `Document.save`：`save` 语义绑定 buffer/EOL/encoding，强塞会改 L0 公共面；文件数受结果集约束，重复 ~15 行可接受（避免过早抽象） |

## 三、分步实施

### 步骤 1：改 `yate/editor_view/find_replace.py` `_replace_on_disk`

输入：评审记录 MAJOR-1 / MAJOR-2。
改动：`text.split("\n")` 切行；`new_lines is lines` 免写契约不变；
`"\n".join(new_lines).encode("utf-8")` → `mkstemp(dir=path.parent,
prefix=path.name + ".yate-tmp-")` → `os.fdopen(fd, "wb")` 写入 →
`shutil.copystat(path, tmp)` → `os.replace(tmp, path)`；OSError 分支
`tmp.unlink(missing_ok=True)` + `log.warning`；新增 `os` / `shutil` /
`tempfile` 导入。
输出：字节级保真 + 原子落盘。
验收：步骤 3 全绿。

### 步骤 2：回归用例（`tests/test_app_find_replace.py` 追加 2 个）

- `test_replace_on_disk_preserves_crlf_and_unicode_separators`：
  CRLF 文件 + 含 `\u2028` 的行；`a` 替换 needle；断言磁盘字节除命中
  附近外与原文件一致（`\r\n` 全保留、`\u2028` 原样、替换生效）。
- `test_replace_on_disk_atomic_no_temp_left`：替换后目标目录无
  `*.yate-tmp-*` 残留（成功路径 `os.replace` 消费临时文件）。

### 步骤 3：验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_app_find_replace.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

全部退出码 0。

## 四、风险与回滚

- `split("\n")` 后行内含 `\r`，`search_lines` 的列坐标对含 `\r` 行
  与 search 阶段（splitlines）不一致——仅影响显示片段（snippets 仍按
  splitlines 取行），替换不受影响（replace 阶段自检索）；用例 1 锚定。
- 回滚：单提交 revert（改动集中在 `_replace_on_disk` + 2 个测试）。

## 五、第二轮修复（code-review-expert 轮，2026-10-16）

输入：评审记录三轮（code-review-expert：3 MAJOR + 4 MINOR）。
非目标：两条既有 follow-up（命中文件二次读盘、空替换守卫）维持缓办；
不改 `SearchEngine.replace_all` 的 backreference 语义（m1 仅补披露）。

| # | 发现 | 修复 | 文件 |
|---|---|---|---|
| F3 | M1 `reveal_match` 行越界：`buf.lines[row]` 先于 `set_cursor` 钳制求值，buffer 未保存删行后 enter 崩溃 | 索引前 `row = min(row, len(buf.lines) - 1)` | editor.py |
| F4 | M2 搜索侧/片段侧 `splitlines()` 与 TextBuffer/替换侧 `split("\n")` 行视图不一致（reveal 错行、CRLF `$` 正则搜索/替换矛盾） | `_search_one_file` 与片段构建统一 `split("\n")`（docstring 注明 TextBuffer 语义）；片段行仅显示侧 `rstrip("\r")`；engine 2 条 + pilot 1 条对齐测试 | project_search.py、find_replace.py |
| F5 | M3 结果面板无滚动跟随：命中超一屏后 `>` 光标不可见 | `#fr-results` 加 `overflow-y: auto`；渲染时记录 `_cursor_line`（0 基内容行号），渲染后 `scroll_to(y=..., animate=False)`；pilot 测试锚定 | find_replace.py、find-replace-screen.tcss |
| F6 | m2 walk 5000 文件上限静默截断，结果可能不完整而不告知 | 新常量 `SCAN_FILE_CAP = 5_000` 显式传 `walk_files(limit=...)`；`len(paths) >= cap` 置 `_truncated`；结果面板尾部 dim 提示行；monkeypatch walk 测试 | find_replace.py |
| F7 | m3 replace worker 内 `_replace_open` 重读实时输入与选项（`_query()` / `self._case`），与磁盘路径的模式快照漂移 | `_replace_scope` 在 UI 线程构造快照：engine（选项定型）+ find 文本 + replacement 一并传 worker，`_replace_open` 改收参数 | find_replace.py |
| F8 | m4 `_replace_scope_all` 以 `list + in` 去重，O(n²) 且在 UI 线程 | `list(dict.fromkeys(...))` 保序去重 | find_replace.py |
| F9 | m1 跨匹配边界断言（lookaround 越出命中段）计数虚增——与 `SearchEngine.replace_all` 既有取舍一致 | `replace_lines` docstring 补披露一句 | project_search.py |

### 新增测试

- engine（tests/test_project_search.py）：`\u2028` 文件按 `\n` 视图返回
  row/col；CRLF 文件 `$` 锚正则与 buffer 视图一致（不命中）+ 字面命中
  行列对照。
- pilot（tests/test_app_find_replace.py）：`\u2028` 渲染行号 `1:`；
  down 多次后 `#fr-results` scroll 偏移 > 0；monkeypatch walk 5001 路径
  出现截断提示；开文档删行后 enter 落钳制行不崩溃。

### 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_project_search.py tests/test_app_find_replace.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

全部退出码 0。

### 风险与回滚

- `split("\n")` 后搜索侧行尾含 `\r`：字面查询不受影响；`$` 锚正则从
  "搜索命中/替换不命中"的矛盾态变为两侧一致不命中（与 buffer 语义对齐，
  原行为才是漂移）；片段显示 `rstrip("\r")` 不受影响。
- `_cursor_line` 滚动为新渲染路径，既有结果渲染测试（分组/标记/片段）
  回归锚定。
- 回滚：单提交 revert（改动集中在 project_search.py / find_replace.py /
  editor.py / tcss + 测试）。
