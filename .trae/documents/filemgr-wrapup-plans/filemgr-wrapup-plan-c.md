# plan-c：遗留清扫（R3）

依赖：无（与 plan-a 可并行；涉及 `scenarios/filemanager.py` / `tests/test_filemgr.py` 的改动排在 plan-a / plan-b 之后执行以避撞）。

## c-1 is_mounted 死守卫 9 处

背景：Textual 8.2.8 的 `Widget.is_mounted` 只置 True 从不复位（unmount 不清），死守卫不拦截任何路径。处置按 m9 同法二选一：换 `is_attached`，或保留并 docstring 注明 defensive redundancy。**逐处定稿**：

| 文件:行 | 上下文 | 倾向 |
|---|---|---|
| `manual.py:487` | 渲染守卫 | 甄别 worker/回调上下文 → `is_attached` |
| `manual.py:493` | 同上 | 同上 |
| `manual.py:578` | `not source or not self.is_mounted` | 同上 |
| `manual.py:590`（原 :587） | 同上 | 同上 |
| `manual.py:690` | `query is None or not self.is_mounted` | 同上 |
| `find_replace.py:390` | worker 回调画守卫 | `is_attached` |
| `find_replace.py:554` | 同上 | `is_attached` |
| `highlighting.py:407` | **注意**：本类在 :106 有自有 `is_mounted` property（镜像宿主 widget），`self.is_mounted` 走的是该 property 而非 Textual 原生 | 甄别：若宿主 widget 可达且 `host.is_attached` 语义等价则换；否则保留 + docstring 注明 |
| `highlighting.py:434` | 同上 | 同上 |

既有先例（照抄口径）：`filemgr.py:452` / `palette.py:236` 的注释——"is_mounted never resets on unmount; is_attached mirrors Textual's own mount check"。

执行步骤：

1. 逐处读上下文（是否在 worker / call_after_refresh 回调内），定稿 `is_attached` 或 docstring 注明；
2. `grep -rn "\.is_mounted\b" yate/` 复核全清单，结果与逐处处置落盘本文档「执行记录」节（`editor.py:253` 的 `lambda: ed.mounted` 注入与 `panes.py` 的注入形参不在 issue 清单内，不动；`completion_flows.py` / `commandline.py` 命中的是 popup widget 的 `is_mounted`，同样不在清单内，不动——如顺手核实其同样只置 True，仅登记不改）；
3. `tests/test_filemgr.py` 风格不新增死守卫测试；既有测试全绿即可。

## c-2 filemgr 测试宿主去重（issue 表述偏差登记）

issue 原文："new_app 加 `filemanager_dir` 形参消除 filemgr 用例自建宿主重复"。

考古事实：`new_app` 实际在 `tools/smoke_test/harness.py:361`（签名 `target/keymap/theme_name/config`），**不在 conftest**；filemgr 单测宿主是 `tests/test_filemgr.py` 本地 `_Host` + `_screen` 辅助。偏差登记于本节，执行按实际落点裁量：

1. `tools/smoke_test/harness.py::new_app` 增加可选形参 `filemanager_dir: Path | None = None`：非 None 时启动后打开 filemanager 屏并返回 `(app, screen)`（或按 harness 现有返回形态最小扩展），smoke 场景 `filemanager.py` 改用之；
2. `tests/test_filemgr.py` / `tests/test_app_filemgr.py` 的本地 `_Host`/`_screen` 重复：若两文件各自复制了等价宿主，抽到测试共享处（tests 内模块级 helper 或 conftest fixture——**不建 Protocol**、不建共享类型层，只传具体对象/函数）；若仅一处本地宿主（无重复），则登记"无重复可消除"并只做第 1 步，不过度工程。

## c-3 filemanager SVG 冒烟基线

事实：`tools/smoke_test/scenarios/filemanager.py` 已在 :106 调 `snapshot_svg`，但 `tools/smoke_test/smoke_baselines/` 无 filemanager 基线文件（其余 121 场景均有 `<scenario>.json`）。

步骤：

1. 读 `tools/smoke_test/baselines.py` 与 CLI 入口，确认基线登记机制（`--baseline` / `--with-svg` 类开关）；
2. **只对 filemanager 场景**登记基线（禁止全量 snapshot——master 存量 5 处漂移登记，见项目记忆；全量重登会把漂移洗白）;
3. 冒烟门禁按总纲跑全量 121+ 场景，filemanager 场景应从"无基线跳过比对"变为"基线比对通过"。

## 验收

- 五项门禁全绿；
- `grep -rn "\.is_mounted\b" yate/` 输出与执行记录清单一致（清单外零新增）；
- 冒烟 filemanager 场景基线在位且通过。

## 回滚

单提交 `refactor(editor-view): sweep dead is_mounted guards and filemgr test hosts`（如 c-1/c-2/c-3 分开提交更佳：`refactor(editor-view): drop dead is_mounted guards`、`test(smoke): register filemanager svg baseline` 等）；失败 reset 到波起点。
