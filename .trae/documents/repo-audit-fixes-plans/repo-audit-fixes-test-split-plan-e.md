# 子计划 plan-l：巨型测试文件拆分（A7）

> 所属波次：**wave-5**（与 ci-plan-e 文件不重叠，可并行；子代理执行）。
> 执行者：**子代理**（仅 `tests/`）。
> 来源：评审 A7。

## 一、输入

- `tests/test_app_textual.py` 实测 **5222 行**（205.76 KB），为第二名 `test_vim_keymap.py`（1663 行）的 3 倍；同文件内按功能域高度分区（explorer / terminal / panes / find / screensaver / palette 等）；
- 仓库已有拆分先例：editor-split（`yate/editor.py` 1425→882）证明路径可行；
- 拆分是**纯移动 + import 调整**，行为零变化；conftest helper（`wait_until` / `make_key_ui` 等，`tests/conftest.py:66-124`）直接复用。

## 二、独占文件清单

1. `tests/test_app_textual.py`（瘦身为壳：共享 fixture / pilot 基建 + 保留通用外壳行为用例）
2. 新增：`tests/test_app_explorer.py`、`tests/test_app_terminal.py`、`tests/test_app_panes.py`、`tests/test_app_find.py`、`tests/test_app_screensaver.py`、`tests/test_app_palette.py`（功能域以实际分区为准，子代理按类/区块边界裁剪，目标单文件 ≤1200 行）
3. 不改动：`tests/conftest.py`（helper 零修改，仅 import 复用）

## 三、执行步骤（铁律：纯移动）

1. 通读 `test_app_textual.py`，按模块级注释分区与测试类边界列出功能域清单（执行报告中给出"域 → 起止行 → 目标文件"映射表）；
2. 按域 `git mv` 不可用（内容拆分），改为复制代码块到新文件 + 原文件删除，逐域进行；每域迁移后立即跑该域用例；
3. import 归置：每个新文件自带所需 import（含 conftest helper 与模块级 fixture）；文件级 fixture（如 pilot 启动 helper）留在 `test_app_textual.py` 或提升到 conftest——**优先提升到 conftest** 若被 ≥2 个新文件使用（这是唯一的 conftest 追加，helper 为搬运非新写）；
4. `test_app_textual.py` 保留：模块 docstring（改写为"外壳通用行为 + 指向各功能域文件"）、共享基线 fixture、不属于任何域的散用例；
5. 每步验证：`pytest tests/test_app_textual.py tests/test_app_<domain>.py -q` 通过后再进行下一域。

## 四、测试与验证方案

不新增测试（纯移动）。行为零变化的判定标准：

1. **用例数守恒**：迁移前后全仓收集的测试用例集合逐字一致——
   ```powershell
   .venv\Scripts\python.exe -m pytest tests/ --collect-only -q > before.txt   # 拆分前
   .venv\Scripts\python.exe -m pytest tests/ --collect-only -q > after.txt    # 拆分后
   ```
   两文件排序后 `Compare-Object` 零差异（node id 的模块前缀变化属预期，比较时剥离路径前缀只比 `::Class::test` 尾段与数量）；
2. 验证命令（退出码 0）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_app_textual.py tests/test_app_explorer.py tests/test_app_terminal.py tests/test_app_panes.py tests/test_app_find.py tests/test_app_screensaver.py tests/test_app_palette.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pyright tests/
```

3. 手工验证：`git diff --stat` 确认删除行数 ≈ 新文件合计行数（无夹带改写）；抽 3 个迁移用例 diff 逐字比对断言未动。

## 五、风险与回滚

- 风险 R5（主计划）：漏搬 / 夹带修改 → 用例数守恒 + 逐字 diff 审查；子代理并发跑 pytest 的 timing 干扰（subagent-workflow §三.3）→ 验收命令限定本子计划文件，全量回归归 wave-6。
- 回滚：单提交 revert；`test_app_textual.py` 原文可在 revert 后完整恢复。
- 登记项：wave-1 plan-a 豁免名单与 A17 README 若引用了 `test_app_textual.py` 的范围描述，由主代理在 wave-6 回填（测试文件名变化不影响其语义）。
