# cd 命令方案（:cd 快速切换盘符与目录）

> 状态：已批准（无人值守续作，2026-11-01 用户指令）。
> 规模：中小任务（L3 薄方法 + L4 命令注册 + 补全 + 测试 + 双语手册），单计划不拆波次。
> 分支：`feat/file-manager` 续作（与 file manager 切换语义强耦合，分支未推送）。

## 一、语义定稿

| 输入 | 行为 |
|---|---|
| `:cd <dir>`（相对/绝对/`~`/盘符根如 `D:\`） | 解析（`resolve_input_path`：`~` 展开、相对按 workspace root）→ 存在且是目录 → 复用 `open_path` 目录分支（`set_root` + `refresh_tree` + reveal + focus + `opened folder` 消息）；**不动已开 tab**（对齐 explorer 点目录语义，无数据丢失风险，不需 dirty 门禁） |
| `:cd <file>` / `:cd <不存在>` | `not a directory: <resolved>`（warn），root 不变 |
| `:cd`（无参） | `workspace root: <root>`（info），不改状态 |

- 盘符支持免费获得：`Path("D:\\")` 是绝对目录，`set_root` 直接可用。
- 与 `:e` 的差异：`:e <file>` 打开文件、`:e <dir>` 切根；`:cd` 只接受目录（vim 语义）。

## 二、架构落点

1. **L3**（策略下沉 owning 模块，commands 不做文件系统判定）：
   `DocumentFlows.open_directory(path: Path) -> None`（`document_flows.py`，
   `open_path` 之后追加）——resolve → OSError 安全探测 is_dir → 非目录
   `self._report(f"not a directory: {resolved}", "warn")` + return →
   目录 `self.open_path(resolved)`。零新注入（复用既有 resolve/_report）。
2. **L4**：`commands.py`：
   - `_cd(args)`：无参 → `editor.message(f"workspace root: {editor.workspace.root}", kind="info")`；
     有参 → `editor.document_flows.open_directory(Path(args.strip()))` (errata: real attribute is `document_flows`, editor.py:442)；
   - `reg("cd", _cd, "change the workspace root directory (:cd [dir]; bare :cd shows it)",
     arg_completer=_make_cd_completer(editor))`（注册在 `:e`/`:edit` 组之后）。
3. **补全**：`_make_cd_completer(editor)`（commands.py，`_make_path_completer` 旁）——
   `path_matches(prefix, editor.workspace)` 结果 + 盘符候选
   （`workspace.list_drives()`，wave-1 产物；`str(d.path)` (errata: Path str already carries the trailing separator; appending `os.sep` would double it)，
   `d.name.lower().startswith(prefix.lower())` 且不等于 prefix 去重）。
   不改共享 `_make_path_completer`（:e/:split 零影响）。空 prefix →
   root 子项 + 全部盘符（「快速切换盘符」入口）。
4. **手册**：`manual.en.md` / `manual.zh.md` 命令表 `:e` 条目附近加 `:cd` 行（双语同步）。
5. **架构守卫**：无新 editor_view import（无 UI_FROZEN_FILES 变更）；L4→L0
   `path_matches`/`list_drives` 为既有合法方向；R12 日志不需要（薄转发）。

## 三、测试（tests/test_cmd_cd.py，对齐 test_set_options.py 构造模式）

| 用例 | 操作 | 断言 |
|---|---|---|
| `test_cd_switches_root_and_refreshes_tree` | `:cd <tmp sub>` | `workspace.root == sub`；explorer 刷新被调 |
| `test_cd_accepts_drive_root` | monkeypatch `list_drives` + `:cd <盘符路径形态>`（win-only skipif） | root 切到盘符根 |
| `test_cd_rejects_file_with_warning` | `:cd <文件>` | root 不变；report warn 含 `not a directory` |
| `test_cd_rejects_missing_path` | `:cd <不存在>` | root 不变；report warn |
| `test_cd_bare_shows_root` | `:cd` | message 含当前 root；root 不变 |
| `test_cd_completer_lists_dirs_and_drives` | prefix `""` / `"d"` / `"C:\"`（monkeypatch drives） | 目录候选 + 盘符候选；无重复 |
| `test_cd_relative_resolves_against_root` | root=tmp 下 `:cd sub` | root == tmp/sub |

## 四、验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/flows/document_flows.py yate/commands.py tests/test_cmd_cd.py
.venv\Scripts\python.exe -m pytest tests/test_cmd_cd.py tests/test_set_options.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
```

## 五、风险与回滚

- `os` import 若 commands.py 缺失则补（stdlib）；
- 盘符补全在 POSIX 返回空列表（list_drives 既有契约），无平台分支；
- 回滚：三处追加式小改 + 新测试文件，独立成笔 revert 零残留。
