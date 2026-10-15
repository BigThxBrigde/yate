# find-replace-review-fixes-plan

> 来源记录：[`.trae/reviews/2026-10-16-find-replace-pr1.md`](../reviews/2026-10-16-find-replace-pr1.md)
> （第一轮 PR 预审，2 MAJOR）。修复范围仅磁盘替换路径与回归测试。

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
