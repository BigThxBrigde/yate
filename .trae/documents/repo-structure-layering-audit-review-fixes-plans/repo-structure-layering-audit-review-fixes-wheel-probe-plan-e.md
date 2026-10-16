# 子计划 e —— wheel 资源清单取证（Fix-D2 / 审计 S-11）

- 总纲：[`overview.md`](overview.md)｜主计划：[`../repo-structure-layering-audit-review-fixes-plan.md`](../repo-structure-layering-audit-review-fixes-plan.md)
- 波次：wave-3｜独占文件：无（**只读取证**，产物为结论文本；构建输出写临时目录）
- 前置依赖：wave-1 / wave-2 完成（本步不改仓库文件）

## 一、目标

验证 `yate/resources/`（无 `__init__.py` 的命名空间目录）与 `yate/docs/`、
`yate/extensions/*.example` 是否被 hatchling 打进 wheel —— 即
`pyproject.toml` 中 `[tool.hatch.build.targets.wheel]` 条目下注释的声明是否成立。

## 二、步骤（可复制执行）

```powershell
# 1) 隔离构建（pip 自动在临时环境安装构建后端 hatchling，不污染本 worktree 的 .venv）
$out = Join-Path $env:TEMP 'yate-wheel-probe'
New-Item -ItemType Directory -Force -Path $out | Out-Null
.venv\Scripts\python.exe -m pip wheel . --no-deps -w $out

# 2) 列出 wheel 内的资源条目并与 pyproject 声明比对
.venv\Scripts\python.exe -c "import glob, zipfile, pathlib; w = sorted(glob.glob(str(pathlib.Path(r'$out') / 'yate-*.whl')))[-1]; z = zipfile.ZipFile(w); names = z.namelist(); [print(n) for n in names if n.startswith(('yate/resources/', 'yate/docs/', 'yate/extensions/'))]; print('TOTAL', len(names))"
```

- 期望条目：`yate/resources/*.tcss`（16）、`yate/resources/manual.*.md` / `changelog.*.md`（4）、
  `yate/docs/*.md`（9）、`yate/extensions/*.example`（9）+ `_yate.lua` / `_yate.d.lua`；
- 判定：上述条目齐备 = 声明成立（S-11 关闭）；缺项 = 记录缺项清单并在主计划 §七 登记为
  待办（本轮**不改** `pyproject.toml`，须另立方案）；
- 兜底（无网络 / 构建后端不可得）：记录实际报错与退出码，结论登记为**未验**并说明原因；
  **不得**为此改动 `pyproject.toml`、项目依赖或环境。

## 三、输出

- wheel 文件路径（临时目录，不入库）、资源条目清单、`TOTAL` 计数、退出码；
- 结论（三选一）：声明成立 / 缺项清单 / 未验（附原因）。

## 四、风险与回滚

- 只读取证 + 临时目录产物：不留仓库改动；如需清理，删除临时目录即可；
- 若 pip 构建因网络失败：按 §二 兜底，不重试第二次以上、不安装任何依赖。
