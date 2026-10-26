# Hex View - Plan A: is_text_file 语义变更

## 目标

修改 `Workspace.is_text_file()` 的语义：未知扩展名文件也读前 2048 字节嗅探（UTF-8 可解码 + 无 NUL 字节），
不再以扩展名白名单作为第一道门槛——文本文件一律可以打开。

## 非目标

- 修改 `TEXT_SUFFIXES` 白名单本身（保持现状）；
- 修改调用方行为（本波次只改嗅探逻辑与对应测试）。

## 输入

- `yate/services/workspace.py:388-411`（`is_text_file` 当前实现）；
- `tests/test_workspace_filter.py:486-490`（`test_is_text_file_rejects_unknown_suffixes`）。

## 独占文件清单

- `yate/services/workspace.py`（修改 `is_text_file`）；
- `tests/test_workspace_filter.py`（改写测试）。

## 具体修改

### 1. 修改 `yate/services/workspace.py:388-411`

**当前逻辑**：
```python
@staticmethod
def is_text_file(path: Path) -> bool:
    """Best-effort check that *path* is editable text."""
    name = path.name.lower()
    if name in ("dockerfile", "makefile", "readme", "license"):
        return True
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    if path.suffix == "":
        # Extension-less files: sniff the first bytes.
        try:
            with path.open("rb") as fh:
                chunk = fh.read(2048)
            try:
                chunk.decode("utf-8")
            except UnicodeDecodeError as exc:
                chunk[: exc.start].decode("utf-8")
            return b"\x00" not in chunk
        except (OSError, UnicodeDecodeError):
            return False
    return False
```

**新逻辑**：
```python
@staticmethod
def is_text_file(path: Path) -> bool:
    """Best-effort check that *path* is editable text.

    Known suffixes (TEXT_SUFFIXES) and conventional names (dockerfile, ...)
    are trusted without sniffing.  Every other file (unknown suffix or
    extension-less) reads the first 2048 bytes: UTF-8 decodable + no NUL
    byte => text.  This prevents unknown-suffix text files from being
    misclassified as binary.
    """
    name = path.name.lower()
    if name in ("dockerfile", "makefile", "readme", "license"):
        return True
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    # Unknown suffix or extension-less: sniff the first bytes.
    try:
        with path.open("rb") as fh:
            chunk = fh.read(2048)
        try:
            chunk.decode("utf-8")
        except UnicodeDecodeError as exc:
            # The 2048-byte cut can land inside a multi-byte UTF-8
            # sequence; retry without the truncated tail before
            # calling a legitimate (e.g. Chinese) text file binary.
            chunk[: exc.start].decode("utf-8")
        return b"\x00" not in chunk
    except (OSError, UnicodeDecodeError):
        return False
```

**变更点**：移除 `if path.suffix == "":` 条件，让嗅探逻辑覆盖所有非白名单文件。

### 2. 改写 `tests/test_workspace_filter.py:486-490`

**当前测试**：
```python
def test_is_text_file_rejects_unknown_suffixes(tmp_path: Path) -> None:
    """A suffix outside the text list is not editable."""
    unknown = tmp_path / "thing.weird"
    unknown.write_text("x\n", encoding="utf-8")
    assert not Workspace.is_text_file(unknown)
```

**新测试**：
```python
def test_is_text_file_sniffs_unknown_suffixes(tmp_path: Path) -> None:
    """An unknown suffix falls back to content sniffing."""
    # Text content => accepted
    unknown_text = tmp_path / "thing.weird"
    unknown_text.write_text("hello\n", encoding="utf-8")
    assert Workspace.is_text_file(unknown_text)

    # Binary content => rejected
    unknown_bin = tmp_path / "thing.weird2"
    unknown_bin.write_bytes(b"\xff\xfe\x00binary")
    assert not Workspace.is_text_file(unknown_bin)
```

## 输出

- `Workspace.is_text_file()` 对未知扩展名文件也做内容嗅探；
- 测试覆盖正反路径。

## 验收命令

```powershell
cd D:\Programming\yate-hex-view
.venv\Scripts\python.exe -m pytest tests/test_workspace_filter.py -q -n auto
.venv\Scripts\python.exe -m pyright yate/services/workspace.py tests/test_workspace_filter.py
```

通过判定标准：
- pytest 退出码 0，所有用例通过；
- pyright 零诊断。

## 风险清单

| 风险 | 缓解 |
|---|---|
| 未知扩展名的二进制文件被误判为文本（如 .exe 内容恰好 UTF-8 可解码） | 2048 字节嗅探 + NUL 字节检查，误判概率极低；即使误判，用户仍可用 `:hex` 切换 |
| 性能影响（每个未知扩展名文件都要读 2048 字节） | 嗅探只在非白名单文件触发，白名单文件仍快速路径；2048 字节读取开销可忽略 |

## 回滚路径

恢复 `if path.suffix == "":` 条件即可回滚。

## 触碰架构边界

- 无（`Workspace` 是 L0 叶子，修改内部逻辑不触碰分层边界）。

## 【执行】【审核】迭代记录段

- 2026-10-24 主代理复核：plan-a 无需实质修订，嗅探逻辑变更与测试改写方向正确。
