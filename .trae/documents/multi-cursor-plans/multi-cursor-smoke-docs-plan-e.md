# multi-cursor plan-e：冒烟场景、双语手册与体量回填（收尾）

> wave-3。依赖：plan-a、plan-b、plan-c、plan-d 全部验收通过。
> 输入：总纲 §九（总门禁与手工验证清单）、§六（废弃清单）。

## 一、输入

- 冒烟基建：`tools/smoke_test/scenarios/_base.py`（ScenarioResult/Check）、
  `vim_advanced.py`（`_vim_state`/`mode_label` 断言范式 :32-139）、
  `__init__.py`（场景注册表）。
- 手册：`yate/docs/manual.en.md` / `manual.zh.md`（键位文档章节）。
- 体量豁免名单（规则 `architecture-boundaries.md` §三.7 与
  `tests/test_architecture.py` `SIZE_EXEMPT_FILES` 两处同步维护）。

## 二、独占文件清单

只改以下文件，不要动其它任何文件：

| 文件 | 改动 |
|---|---|
| `tools/smoke_test/scenarios/multi_cursor.py`（新） | vim/vsc 多光标冒烟场景 |
| `tools/smoke_test/scenarios/__init__.py` | 注册新场景 |
| `yate/docs/manual.en.md` | 多光标键位章节 |
| `yate/docs/manual.zh.md` | 同步中文（双语同步硬约束） |
| `.trae/rules/architecture-boundaries.md` | §三.7 豁免名单行数回填（仅行数数字） |

## 三、具体修改

### 3.1 冒烟场景（tools/smoke_test/scenarios/multi_cursor.py）

两个场景函数，范式与 `_vim_visual_mode_ops` 一致（pilot.press +
`app.editor.mode_label()` + buffer 直读断言 + `snapshot_svg`）：

1. `_vim_multi_cursor_ops(tmp)`：
   - 开场 buffer `"alpha beta\ngamma delta\nepsilon zeta"`；
   - `pilot.press("alt+c")` ×2 → Check：`extra_cursors == [(1,2),(2,2)]`、
     `mode_label()[0] == "V-COLUMN"`；
   - `pilot.press("i")` + `type_text(pilot, "X")` → Check：三行各插 X、
     chip 仍 `V-COLUMN`；
   - `pilot.press("escape")` → Check：`extra_cursors == []`、label 回
     `"NORMAL"`、一次 `buffer.undo()` 复原全部 X；
   - motion 保活：重建点后 `pilot.press("j")` → Check：`cursor` 下移、
     点集不变。
2. `_vsc_multi_cursor_mouse(tmp)`：
   - `MouseDown(meta=True, button=1)` 合成两次（不同行）→ Check：点数 2、
     chip `V-COLUMN`；
   - `pilot.press("x")` → Check：两点同步插入；`pilot.press("escape")`
     → 清点；
   - 普通点击 → Check：点清空 + cursor 移动；
   - undo 一步复原。

注册：`scenarios/__init__.py` 场景表追加两项（命名
`vim_multi_cursor_ops` / `vsc_multi_cursor_mouse`）。

### 3.2 双语手册

`manual.en.md` / `manual.zh.md` 键位章节（vim 段与 vsc 段各一小节）：

- **Multi-cursor (issue IKKJHH)**：`ALT+C`（vim NORMAL / vsc）在下一行
  添加光标；vim `i/a/I/A` 后多点输入；vsc `ALT+click` 加点；打印字符、
  Backspace、Enter 多点协同（Enter 无自动缩进）；方向键只动主光标；
  `ESC` 退出；普通点击收拢；整段多点编辑一次 `Ctrl+Z`/`u` 撤销。
- 已知限制（与总纲 §二一致）：多点回车不自动缩进、无多点选区、无
  bracket 补全。
- 双语**同时**新增、结构对齐（doc-conventions §三）。

### 3.3 体量行数回填（仅数字，不改名单）

按 `architecture-boundaries.md` §三.7 口径（`splitlines()`，含空行）：

```powershell
.venv\Scripts\python.exe -c "print(len(open('yate/editor_core/buffer.py', encoding='utf-8').read().splitlines()))"
.venv\Scripts\python.exe -c "print(len(open('yate/keymaps/vim.py', encoding='utf-8').read().splitlines()))"
```

把实测数字回填 §三.7 豁免名单两处文本（`buffer.py`（原 820 行）与
`keymaps/vim.py`（原 1117 行））；`SIZE_EXEMPT_FILES` 集合不变；
`test_source_files_within_size_threshold` 天然通过。

## 四、测试与验证

### 新增场景的验证

```powershell
.venv\Scripts\python.exe -m tools.smoke_test run --no-color
.venv\Scripts\python.exe -m pytest tests/test_smoke_baselines.py -q
```

- 判定：冒烟场景数（master 实测 `python -c "from tools.smoke_test.scenarios import SCENARIOS; print(len(SCENARIOS))"` = **107**）增至 109，`checks` 全部通过、退出码 0；
  `test_smoke_baselines.py` 若快照计数断言需同步更新（场景注册数），
  在本子计划内一并改（属于 §二清单精神内的冒烟基建联动——若该测试
  硬编码场景数，更新之；不在清单文件时先上报主代理再改）。

### 手册验证

- 纯文档：无测试；复核双语结构对齐（章节成对、术语一致）。

### 收尾总门禁（主代理在 plan-e 验收后执行，总纲 §九）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m tools.smoke_test run --no-color
```

外加手工验证（总纲 §九清单：vim/vsc 各五步），无法自动化的部分按
清单逐项在 Windows Terminal 实测并记录。

## 五、风险与回滚

| 风险 | 缓解 |
|---|---|
| 冒烟场景数快照断言（test_smoke_baselines）失配 | 先跑一遍确认断言形态再注册；需改清单外文件时停下上报 |
| pilot 对 `alt+c` 的合成键名与真机不一致 | pilot 合成的是 `Key("alt+c")` 事件（与驱动产物同名）；真机差异归手工验证清单 |
| 手册双语漂移 | 同一 commit 内成对修改；引用总纲术语表 |
| 行数回填口径错 | 用 `splitlines()`（守卫口径）实测回填，不估算 |
| 回滚 | 独立 commit `test(smoke): multi-cursor scenarios` + `docs(manual): multi-cursor keys`（分两笔，按 `git-commit-message.md`）；`git revert` 净回 |

## 六、验收标准

1. 冒烟 109 场景全过、退出码 0；
2. 总门禁四条命令退出码 0（pyright 零诊断 / pytest 全绿 / 架构 28 用例
   / 冒烟基线）；
3. 手册双语成对、无单独成章；
4. 规则文本行数与 `splitlines()` 实测一致；
5. 总纲 §九手工验证清单逐项执行并记录（vim/vsc 各步、Ctrl+Z 一步撤销、
   单光标回归）。
