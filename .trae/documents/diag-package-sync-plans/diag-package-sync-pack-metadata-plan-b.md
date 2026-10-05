# plan-b：冻结构建补 yate dist-info（wave-1）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。

## 一、独占文件清单

只改以下两个文件，不动其它任何文件：

- `pack/yate.spec`
- `pack/yate-onefile.spec`

## 二、现状取证（文件:行号）

- ](../../../pack/yate.spec#L71-L80)：ts 循环对
  `tree_sitter` / `tree_sitter_python` / `tree_sitter_bash` 逐个
  `copy_metadata(_ts_pkg)`，注释明说 dist-info 供 `importlib.metadata.version()`
  探测使用——**未带 yate 自身 dist-info**；
- ](../../../pack/yate-onefile.spec#L78-L87)：同构循环，
  同样缺失；
- `datas` 汇总点：](../../../pack/yate.spec#L104-L114) 与
  onefile spec 的 `Analysis(datas=datas + ts_datas, ...)`；
- 后果：plan-a 落地后，exe 内 `importlib.metadata.requires("yate")` 会抛
  `PackageNotFoundError`，`[packages]` 节降级为 `<probe failed>` —— 冻结
  路径回归，必须随 plan-a 一起补齐。

## 三、具体修改（两个 spec 同构）

在 ts 循环之后追加一段（yate.spec 约在 80 行后、onefile spec 约在 87 行后）：

```python
# yate's own + core dependencies' dist-info: diagnostics._section_packages
# derives the [packages] inventory from importlib.metadata.requires("yate")
# and probes the versions with importlib.metadata.version() -- both read
# dist-info metadata that must ship inside the frozen app (issue IKJJFI).
# Without the core entries the exe reports bundled packages (pyperclip)
# as "not installed"; textual is also covered by a contrib hook, duplicate
# datas entries are deduplicated by PyInstaller.
yate_datas = copy_metadata("yate")
for _core_pkg in ("pyperclip", "textual"):
    yate_datas += copy_metadata(_core_pkg)
```

并把 `Analysis` 的 datas 参数由 `datas + ts_datas` 改为
`datas + ts_datas + yate_datas`。

不改 ts 循环本体（Windows blocked-version 守卫与 `--diag` 的 `version()`
定点探测继续依赖那三份元数据）。

> 迭代记录（wave-2 冻结冒烟发现）：初版只带 `copy_metadata("yate")`，exe 内
> 节渲染正常但 `pyperclip : not installed`（代码已打入、dist-info 未带）；
> 追加 core 依赖 dist-info 循环后复测通过。

## 四、验证方案

| 目标 | 命令 | 通过判定 |
|---|---|---|
| 静态确认（wave-1 内） | 代码评审：两 spec 均含 `copy_metadata("yate")` 且并入 datas | 评审通过 |
| 冻结联合冒烟（wave-2，构建耗时较长故后置） | `powershell -File pack\pack.ps1` | 构建成功，产物 `dist\yate\yate.exe` |
| exe 内 packages 节（wave-2） | `dist\yate\yate.exe --diag` | `[packages]` 节渲染正常：含 `core:` 标签、pyperclip 行，无 `<probe failed: PackageNotFoundError: yate>` |

说明：`pack\pack.ps1` 默认 onedir 模式（`dist\yate\yate.exe`）；脚本自检
`.venv\Scripts\python.exe`，PyInstaller 缺失时自动 `pip install -e ".[build,ts]"`
（worktree 沙箱内执行，不污染全局）。构建失败时如实记录并降级为代码评审
确认，不阻塞 wave-2 其余门禁。

## 五、风险与回滚

- `copy_metadata("yate")` 在构建环境找不到 yate dist-info → PyInstaller
  构建期直接报错，属显式失败（构建环境本就 `pip install -e .`，不成立）；
- 回滚 = revert 两个 spec 的追加段。
