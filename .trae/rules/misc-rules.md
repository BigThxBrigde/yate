---
alwaysApply: true
---

# misc-rules（杂项规则）

收录不成体系但必须遵守的环境与工具约束：单条规则不足以独立成文件时登记在此，
按章节编号追加，不另开新规则文件。

## 一、多行文本：按 Shell 环境选择 here-string 或 heredoc

- **Windows（本项目当前环境）**：Shell 解释器是 **PowerShell**（非 bash/cmd）。
  PowerShell 不支持 `<<'EOF'` / `<<EOF` heredoc 语法，直接使用会报：

  ```text
  ParserError: Missing file specification after redirection operator.
  ```

  多行字符串（典型场景：`git commit -m` 的多行提交信息）必须改用 here-string：

  - `@'...'@`：单引号形式，内容原样保留，不插值（首选，提交信息用这个）；
  - `@"..."@`：双引号形式，支持 `$var` 插值。

  ```powershell
  # 错误：在 PowerShell 里写 bash heredoc，直接 ParserError
  git commit -m "$(cat <<'EOF'
  commit message here
  EOF
  )"

  # 正确：PowerShell here-string
  git commit -m @'
  commit message here
  '@
  ```

  注意：here-string 的结束标记 `@'` / `"@` 必须**顶行书写**（行首不能有空格），
  否则不被识别为结束标记。

- **Linux/macOS（bash/zsh 等 POSIX shell）**：heredoc 是正常语法，可照常使用
  `<<'EOF' ... EOF`。

## 二、Python 代码的测试验证直接用 Python 脚本

对 Python 代码做测试 / 验证时，直接写 Python 脚本执行，不要把验证逻辑硬塞进
PowerShell 命令行拼接（§一 的 PowerShell 语法限制因此大多可以绕开）：

- 解释器统一用项目虚拟环境的 `.venv\Scripts\python.exe`；
- 正式回归跑 `pytest tests/ -q`；一次性探针/冒烟用临时脚本（验证完删除）或
  `python -c "..."` 短表达式。
