# plan SP1 — 声明面 bump（机械，8 文件）

> 从属于[总纲](README.md)；前置：SP0 完成。**本波落地后，总纲 §三的性能收益（3.11 ~1.25× + 3.12 +5%）全额生效。**

## 1. 独占文件清单（只改下列文件，不动其它任何文件）

| # | 文件 | 改动 |
|---|---|---|
| 1 | [pyproject.toml](../../../pyproject.toml) | L10 `requires-python = ">=3.10"` → `">=3.12"`；L47 `pythonVersion = "3.10"` → `"3.12"` |
| 2 | [.github/workflows/test.yml](../../../.github/workflows/test.yml) | `python-version: '3.11'` → `'3.12'`（若矩阵含多版本，确保最低腿 ≥3.12） |
| 3 | [.workflow/test.yml](../../../.workflow/test.yml) | Gitee Go `pythonVersion: '3.11'` → `'3.12'`；L48 注释同步（构建机无 3.12 镜像则停手上报 → D2） |
| 4 | [README.md](../../../README.md) | `Python ≥ 3.10` → `≥ 3.12` |
| 5 | [README.zh.md](../../../README.zh.md) | 同上 |
| 6 | [manual.en.md](../../../yate/resources/manual.en.md) | 同上（打包进 wheel 的用户手册） |
| 7 | [manual.zh.md](../../../yate/resources/manual.zh.md) | 同上 |
| 8 | [python-coding-style.md](../../rules/python-coding-style.md) | **零动作**——§适用范围版本号已随 4fe388c 先行落盘 |

## 2. 不动项

- `ts`/`dev`/`build` extras 的版本约束；`tree-sitter<0.26` 上限及其注释（见 pyproject 注释，与本升级无关）；
- `review.md` 等历史文档中的 `3.10+` 字样（属历史记录）；
- `python-coding-style.md` 条款级内容（归 SP2，已落盘）。

## 3. 验证命令（门禁）

```powershell
.venv\Scripts\python.exe -m pyright yate tests tools        # 0 诊断
.venv\Scripts\python.exe -m pytest tests/ -q                # 连续两次全绿
.venv\Scripts\python.exe -m tools.smoke_test run --fail-only # exit 0
```

pythonVersion 提升后类型语义如有变化，由 pyright 全仓门禁兜住。

## 4. 提交

- 单提交：`chore(project): raise python floor to 3.12`
- 信息体要点：floor 3.10→3.12（pyproject 2 处 + 双 CI 腿 + README/manual 同步）；
  零行为变更；性能动机引用总纲 §三（3.11 ~1.25× 均值提速）。
