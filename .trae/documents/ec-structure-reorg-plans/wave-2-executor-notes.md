# wave-2（theme/ 子包）执行者笔记 —— 检查点

## 已完成步骤（所有编辑均已就地验证）

- b.1 git mv 完成（3 次重命名，R 状态）：
  theme.py -> theme/__init__.py；themes.py -> theme/themes.py；theme_files.py -> theme/files.py
- b.2 theme/__init__.py：docstring L9/L13 + 导入 L43/L49 已更新
- b.3 theme/files.py：docstring L5/L11 + 导入 L22 已更新
- b.4 theme/themes.py：docstring L30 已更新（L26 门面路径未变）
- b.5 消费者：terminal.py:47、manual.py:59、test_theme_trust.py:15/16/23、
  test_theme_files.py:1/19/20 + CHAIN L48（`monkeypatch.setattr(files, ...)` 由 L19 重绑定所要求；作为机械后续项上报）、
  test_theme_palettes.py:456、tools/smoke_test/scenarios/modules.py:10/21/22
- b.6 whichkey.py:17 docstring 已更新
- b.7 test_architecture.py SIZE_EXEMPT_FILES 注释（追加记录式，ASCII）、architecture-boundaries.md L275（门面例外 -> theme/__init__.py）+ L371-376（列表外记录）、wikis/yate-architecture.md L26 + L181
- b.8 目前的验收：
  - pyright yate/ tests/ tools/ -> 0 错误（退出码 0）
  - pytest tests/ -q -n auto -> 退出码 0（无失败）
  - pytest tests/test_architecture.py -q -> 37 passed，退出码 0
  - 残余 grep（计划 b.8 的确切命令）-> 退出码 0，stdout 为空（0 处命中）
  - 冒烟测试：`python -m tools.smoke_test run --no-color --quiet`
    （计划中写的是裸命令 `python -m tools.smoke_test`；工具需要子命令，因此添加了 `run`）-> 121/121 场景、1463/1463 检查，退出码 0
  - pytest tests/ --cov=yate -q -> 已移至后台（id
    e26cf2d26d776184d54a9cfd742bc377），结果尚未确认 - 提交前必须读取
- b.9 准备完成：R15 守卫使用 rglob（test_architecture.py:1565）-> theme/ 子包自动覆盖；theme/ 中没有真正的 R15 载体（grep：theme/ 中无 SCROLLABLE_BASES 类），演练 = 在 theme/themes.py 末尾临时注入类
  `class _R15Drill(ScrollView): pass`，运行
  `pytest tests/test_architecture.py::test_scrollable_widgets_apply_theme_scrollbar_pair -q`
  预期失败并点名 theme/themes.py，然后回退，重跑预期通过
- b.10 完成：门面运行时检查 `import yate.editor_components.theme`
  -> 解析到 theme/__init__.py，所有门面名称均存在（missing []）；
  面向用户的示例 11 处命中（yaterc.example:218、manual.{en,zh}.md 974/889、
  yaterc.{en,zh}.md 178/161/234/211、themes.{en,zh}.md 50/45/183/166）全部未改动，仍为 `from yate.editor_components.theme import ...`
  （计划说 8 处，实测 11 处 - 上报）；cli.py:423 未变
- b.11 未完成：按文件名显式暂存（排除未跟踪的 .trae/documents/ec-structure-reorg-plans/），提交
  `refactor(editor-components): subpackage theme/ (hub + themes + files)`
  （英文，type=refactor，单次提交，不推送）

## 剩余工作

1. 读取后台覆盖率运行结果（预期全部通过，退出码 0）
2. b.9 反向演练（注入 -> 失败 -> 回退 -> 通过）
3. b.11 使用显式路径提交：git add
   yate/editor_components/theme yate/editor_components/terminal.py
   yate/editor_components/manual.py yate/editor_components/whichkey.py
   （旧 theme.py/themes.py/theme_files.py 的删除已被 git mv 作为重命名 R 暂存）tests/test_theme_trust.py tests/test_theme_files.py
   tests/test_theme_palettes.py tests/test_architecture.py
   tools/smoke_test/scenarios/modules.py .trae/rules/architecture-boundaries.md
   .trae/wikis/yate-architecture.md
   注意：add 前先执行 git status --porcelain；旧文件删除 + 新文件：
   验证重命名仍被识别（git status 显示 R  theme.py -> theme/__init__.py 等）
4. 最终报告：重命名列表 + 命令/退出码 + 演练结论 + 偏离项（冒烟 run 子命令；test_theme_files.py:48 链；11 对 8 的文档示例；演练载体 = 按任务负责人指示在 themes.py 中注入的类，因为计划中的载体没有 R15 匹配项）
