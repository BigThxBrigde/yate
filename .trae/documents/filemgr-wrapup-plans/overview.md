# filemgr-wrapup 计划总纲

- 来源 issue：Gitee `IKS4CT`（refactor+perf: 文件管理器收尾——中栏万级条目增量刷新、独立包迁移与遗留清扫）
- 分支：`ref/filemgr-wrapup`（独立 worktree，自 master `4a4f900`，v0.2.16）
- 状态：执行中（方案落盘即批准，无人值守闭环）

## 目标拆分

| 子计划 | 内容 | 依赖 |
|---|---|---|
| [plan-a](filemgr-wrapup-plan-a.md) | R2 包迁移：`editor_view/filemgr.py` + `filemgr_model.py` + `filemgr_keys.py` → `editor_view/filemgr/` 子包（screen / model / keys / \_\_init\_\_），preview.py 不迁 | 无 |
| [plan-b](filemgr-wrapup-plan-b.md) | R1 增量刷新：目录级列表缓存（`(path, show_hidden)` 键 + `mtime_ns` 新鲜度）+ m11 目录预览记忆化 | plan-a（在新包布局上改） |
| [plan-c](filemgr-wrapup-plan-c.md) | R3 遗留清扫：is_mounted 死守卫 9 处、filemgr 测试宿主去重（new_app 形参）、filemgr SVG 冒烟基线 | 无（与 plan-a 并行） |

执行顺序：plan-a → plan-b 串行；plan-c 与 plan-a 可并行（触及文件与 plan-a 无交集）。

## 独占文件清单（波次间不越界）

- **plan-a**：`yate/editor_view/filemgr.py`、`yate/editor_view/filemgr_model.py`、`yate/editor_view/filemgr_keys.py`、新 `yate/editor_view/filemgr/*`、`yate/flows/filemanager_flows.py`（仅导入行）、`tests/test_architecture.py`（仅两处键）、`tests/test_filemgr.py`、`tests/test_filemgr_model.py`、`tests/test_filemgr_flows.py`、`tests/test_app_filemgr.py`（仅导入行）、`tools/smoke_test/scenarios/filemanager.py`（仅导入行）、`yate/resources/filemgr-screen.tcss`（仅头注释）、`yate/docs/file-manager.{en,zh}.md`（仅路径表述）、`.trae/rules/architecture-boundaries.md`（§三.7 豁免行）
- **plan-b**：`yate/editor_view/filemgr/screen.py`、`yate/editor_view/filemgr/model.py`（如需纯函数辅助）、`tests/test_filemgr.py`、`tests/test_filemgr_model.py`（新增缓存测试）、`.trae/reviews/2026-11-01-pr-review-feat-file-manager.md`（不改动，仅引用）
- **plan-c**：`yate/editor_view/manual.py`、`yate/editor_view/highlighting.py`、`yate/editor_view/find_replace.py`、`tools/smoke_test/harness.py`（如采纳 new_app 形参）、`tools/smoke_test/scenarios/filemanager.py`（基线登记；若与 plan-a 撞文件，plan-c 后行）、`tools/smoke_test/smoke_baselines/filemanager*.json`、`tests/test_filemgr.py`（宿主去重；若与 plan-b 撞，plan-c 中该文件改动合并到 plan-b 之后做）

冲突协调：plan-a 与 plan-c 都只改 `scenarios/filemanager.py` 的不同行（导入 vs 基线），但为保证干净仍串行：**a → c → b** 或 **a → b → c**，总执行序定为 **a → b → c**（b 的新测试与 c 的宿主去重同触 `tests/test_filemgr.py`，串行消除冲突）。

## 全局验收门禁（每波后必跑，全部绿才进下一波）

```bash
python -m pyright yate/ tests/ tools/
python -m pytest tests/ -q -n auto
python -m pytest tests/test_architecture.py -q          # 37+ 用例
python -m pytest tests/ -q -n auto --cov=yate --cov-report=term  # coverage >= 75%
python -m tools.smoke_test --help                       # 冒烟（场景数不回退，121 场景）
```

- 性能项（R1/m11）不适用先红后绿：以**全量门禁 + 实测前后数字**锁定，数字回填 plan-b 执行记录。
- 提交纪律：`docs(plans): ...` 与实现分开提交；提交信息英文 conventional；计划文档内禁真实本机路径（相对路径强制）。

## 回滚

每波一个提交点；任一波门禁不可修复时 `git reset --hard <上波提交>` 回退该波，issue 剩余项登记遗留。

## 关键裁决（考古定案）

- Q1 包主文件名 `screen.py`（避免 `filemgr/filemgr.py` 口吃）。
- Q2 目录缓存容量 16（对齐 `PREVIEW_CACHE_SIZE`），缓存 `list[Entry]`，渲染 Text 每次从缓存 entries 重排（主题切换不陈旧）。
- Q3 新鲜度 = 目录 `mtime_ns` 复验 + `r` 强刷，不做 inotify。
- R1 缓存键须含 `show_hidden`；任何 mutation 路径（create/rename/delete/paste 后 `workspace.invalidate()` + `_reload`）先清缓存。
- issue 表述偏差登记：`new_app` 实际在 `tools/smoke_test/harness.py`（非 conftest）；filemgr 单测宿主是 `tests/test_filemgr.py` 本地 `_Host` + `_screen`。plan-c 按实际落点裁量并在文档登记。
- 冒烟基线缺口：`tools/smoke_test/smoke_baselines/` 无 filemanager 基线（scenario 已含 `snapshot_svg` 调用）；只重登 filemanager 场景基线，勿全量 snapshot（master 存量 5 处漂移登记，见项目记忆）。
