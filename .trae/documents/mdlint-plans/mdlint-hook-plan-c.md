# mdlint git hook + 依赖 (plan_c)

**波次**: wave-1（与 plan_a 并行）

## 一、输入

- plan_a 产出的 `python -m tools.mdlint` CLI；
- 仓库无 `.pre-commit-config.yaml`、无 `.githooks/`、无既有 lint 配置；
- `pyproject.toml` 的 `[project.optional-dependencies] dev` 需新增 `pymarkdownlnt`。

## 二、独占文件清单

**新增**：

| 文件 | 职责 |
|---|---|
| `.githooks/pre-commit` | 仓库自带 pre-commit hook 脚本 |

**修改**：

| 文件 | 改动 |
|---|---|
| `pyproject.toml` | `[project.optional-dependencies] dev` 新增 `"pymarkdownlnt>=0.9.41,<1.0"` |

**新增测试**：

| 文件 | 用例数 |
|---|---|
| `tests/test_githook.py` | ~6 |

**不触碰**：`yate/`、`tools/mdlint/`、`tools/pack/`、`tools/translate/`。

## 三、git hook 设计

### 3.1 脚本内容（`.githooks/pre-commit`）

```bash
#!/usr/bin/env bash
# Pre-commit hook: lint staged Markdown files.
# Enable: git config core.hooksPath .githooks
# Bypass: git commit --no-verify

set -euo pipefail

# Collect staged Markdown files (Added/Copied/Modified only).
FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.md$' || true)
if [ -z "$FILES" ]; then
    exit 0
fi

# Determine language per file and lint.
EXIT=0
for f in $FILES; do
    case "$f" in
        *.zh.md|yate/docs/*.zh.md)
            LANG="zh"
            ;;
        *.en.md|yate/docs/*.en.md|README.md|CHANGELOG.md)
            LANG="en"
            ;;
        .trae/*)
            LANG="zh"
            ;;
        *)
            LANG="en"
            ;;
    esac

    # Fix pass: auto-fix what is fixable.
    python -m tools.mdlint --fix --lang "$LANG" --quiet "$f" || true

    # Re-stage if the file was modified by fix.
    git add "$f"

    # Check pass: any remaining violations?
    if ! python -m tools.mdlint --check --lang "$LANG" --quiet "$f"; then
        echo "mdlint: $f has remaining violations (lang=$LANG)" >&2
        EXIT=1
    fi
done

exit $EXIT
```

**注意**：此脚本为 bash 格式。Windows 上 Git for Windows 自带 bash。
若需 PowerShell 版本，可后续追加 `.githooks/pre-commit.ps1`，但首版只出 bash
（跨平台一致性）。

### 3.2 语言判定规则

| 路径模式 | 语言 |
|---|---|
| `*.zh.md` | zh |
| `*.en.md` | en |
| `.trae/**/*.md` | zh（仓库内部文档以中文为主） |
| `README.md` | en |
| `CHANGELOG.md` | en |
| 其余 `*.md` | en（默认） |

### 3.3 启用方式

```powershell
git config core.hooksPath .githooks
```

**幂等性**：重复执行不报错（git config 覆盖写入）。

### 3.4 绕过

```powershell
git commit --no-verify -m "message"
```

### 3.5 纯文档提交

纯 Markdown 文档提交**会**经过 hook lint。这是预期行为——确保入库的 Markdown
始终合规。若紧急提交可 `--no-verify` 绕过。

## 四、`pyproject.toml` 修改

在 `[project.optional-dependencies] dev` 列表（L24-54）末尾新增：

```toml
    "pymarkdownlnt>=0.9.41,<1.0",
```

位置：L53（`"lupa>=2.0",` 之后）。

## 五、测试用例

### 5.1 `tests/test_githook.py`

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_githook_file_exists_and_executable` | - | `Path(".githooks/pre-commit").exists()` | `True` |
| `test_githook_filters_md_files_only` | 模拟 `git diff --cached` 输出含 `.py` 和 `.md` | hook 脚本逻辑 | 只处理 `.md` 文件 |
| `test_githook_lang_routing_zh` | 文件名 `foo.zh.md` | 语言判定逻辑 | `lang == "zh"` |
| `test_githook_lang_routing_en` | 文件名 `README.md` | 语言判定逻辑 | `lang == "en"` |
| `test_githook_lang_routing_trae` | 文件名 `.trae/documents/plan.md` | 语言判定逻辑 | `lang == "zh"` |
| `test_pyproject_has_pymarkdownlnt_dep` | - | 读 `pyproject.toml` | `dev` 列表含 `pymarkdownlnt` |

## 六、验收命令

```powershell
# 1. pyright strict 零诊断（仅测试文件）
pyright --pythonplatform Windows tests/test_githook.py

# 2. 新增测试全绿
.venv\Scripts\python.exe -m pytest tests/test_githook.py -q

# 3. hook 启用冒烟（手动）
git config core.hooksPath .githooks
git config --get core.hooksPath
# 预期输出: .githooks

# 4. 依赖安装验证
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -c "import pymarkdown; print('ok')"
```

## 七、风险与回滚

| 风险 | 缓解 |
|---|---|
| Windows 上 bash 不可用 | Git for Windows 自带 bash；若缺失则 hook 不执行（`exit 0` 兜底） |
| hook 修改暂存区文件导致意外 `git add` | hook 只 `git add` 被 lint 修改的文件，不影响其余暂存内容 |
| `pymarkdownlnt` 版本冲突 | 锁 `>=0.9.41,<1.0` |
| 回滚 | 删除 `.githooks/` + `git config --unset core.hooksPath` + 从 `pyproject.toml` 删依赖行 |

## 九、执行结果与评审修复（2026-10-20）

1. **非 ASCII 文件名漏检**：`git diff --cached --name-only` 默认对非 ASCII 路径
   输出带引号与八进制转义（如 `"\344\270\255..."`），原 `grep -E '\.md$'` 无法匹配，
   中文名 Markdown 永远不受检查。改为 `-z` + `read -r -d ''` 逐条读取、按 `*.md`
   后缀判定（`--diff-filter=ACM` 不变）。
2. **后端缺失被误判为"有违规"**：pymarkdownlnt 属 dev 可选依赖，缺失时
   `python -m tools.mdlint` 以 traceback 退出 1，hook 会打印"has remaining
   violations"并阻断提交。改为 hook 启动时先 `--list-rules` 探测，失败则
   warning + `exit 0`（与"无解释器"降级同策略）。
3. **退出码 2 只警告不阻断**：`--check` 返回 1（有违规）阻断提交；返回 2
   （该文件 lint 后端崩溃，实测 3 篇真实文档会触发 pymarkdown 自身断言）
   只告警并跳过。
4. **只在确实被改动时重新入暂存区**：fix 后 `git diff --quiet -- "$f"` 判定，
   避免对未变更文件做多余的 `git add`。
