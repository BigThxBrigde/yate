# test-speedup-slow-tests-plan-b：提速最慢测试

**波次**：wave-2（与 plan-c 并行）

## 一、目标

将 Top-5 最慢单元测试（合计 ≈ 52s）降至合理区间，预期总耗时降至 30s 以内。

## 二、非目标

- 不修改产品代码（`yate/editor_term/terminal.py` 等）；
- 不删除或跳过任何测试（所有测试必须保留）；
- 不改变测试的语义（断言的等价形式必须保留）。

## 三、提速策略

### 3.1 `test_ts_backend.py::test_incremental_matches_full_reparse_over_random_edits`（14.67s）

**根因**：20000 步随机增量等价测试（`test_ts_backend.py:1181`），每步都调
`_assert_incremental_matches_full` 做全量 reparse 对比。

**提速方案**：将步数从 20000 降至 5000（4x 提速），保留 `YATE_TS_DIFF_STRESS=1`
环境变量下的 100000 步压力模式。

**改动位置**：[test_ts_backend.py:1181](file:///D:/Programming/yate-test-speedup/tests/test_ts_backend.py#L1181)

```python
# 原代码
groups = 100_000 if os.environ.get("YATE_TS_DIFF_STRESS") == "1" else 20_000

# 新代码
groups = 100_000 if os.environ.get("YATE_TS_DIFF_STRESS") == "1" else 5_000
```

**理由**：5000 步已足够覆盖增量解析的边界情况（随机种子固定为 20260101，可复现）。
`_mutate` 函数（test_ts_backend.py:1134-1162）有 6 种操作（op 0-5）：字符插入/删除、
行插入/删除、整行替换、跳段替换，加上测试自身的 undo 模拟（test_ts_backend.py:1192-1194），
共 7 类编辑形态。5000 步下每类操作预期出现 ≈714 次（5000/7），足以覆盖各种边界情况
（空行、单字符行、多行跳段等）。CI 日常跑无需 20000 步；压力测试留给
`YATE_TS_DIFF_STRESS=1` 手动触发（100000 步，每类 ≈14286 次）。

**预计提速**：14.67s → ≈ 3.7s（4x）。

### 3.2 `test_terminal.py::test_output_buffer_overflow_drains_synchronously_without_loss`（9.10s）

**根因**：喂入 1MB+1 字节（`OUTPUT_BUFFER_LIMIT + 1`）走模拟器解析
（`test_terminal.py:633`），模拟器解析 1MB 数据本身耗时。

**核实结论**：`OUTPUT_BUFFER_LIMIT` 是模块级常量（yate/editor_view/terminal.py:79，
值为 1024*1024），在 `_on_output` 方法中运行时读取（yate/editor_view/terminal.py:207
`if len(self._output_buffer) > OUTPUT_BUFFER_LIMIT`），因此 `monkeypatch.setattr`
修改模块属性即可生效，无需改动产品代码。

**提速方案**：用 `monkeypatch.setattr` 将 `yate.editor_view.terminal.OUTPUT_BUFFER_LIMIT`
改为小值（如 1024），测试喂 `monkeypatched_limit + 1` 字节（1025 字节），overflow 行为
语义完全保留、耗时从 9.1s 降至毫秒级。

**改动位置**：[test_terminal.py:628-643](file:///D:/Programming/yate-test-speedup/tests/test_terminal.py#L628-L643)

```python
# 原代码
def test_output_buffer_overflow_drains_synchronously_without_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exceeding the limit drains at once; no byte is dropped or re-fed."""
    view, scheduled = _coalescing_view(monkeypatch)
    big = b"x" * (OUTPUT_BUFFER_LIMIT + 1)
    view._on_output(big)
    # The drain ran inline: nothing pending, buffer empty, all bytes parsed.
    assert not scheduled
    assert not view._output_buffer
    assert _text(view.emulator).startswith("x" * 64)
    # A following small chunk schedules normally again.
    view._on_output(b"\r\nafter")
    assert len(scheduled) == 1
    scheduled[0]()
    assert "after" in _text(view.emulator)

# 新代码
def test_output_buffer_overflow_drains_synchronously_without_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exceeding the limit drains at once; no byte is dropped or re-fed."""
    # Shrink the limit so the test runs in milliseconds instead of seconds.
    # OUTPUT_BUFFER_LIMIT is read at runtime from the module attribute
    # (yate/editor_view/terminal.py:207), so monkeypatch works.
    small_limit = 1024
    monkeypatch.setattr("yate.editor_view.terminal.OUTPUT_BUFFER_LIMIT", small_limit)
    view, scheduled = _coalescing_view(monkeypatch)
    big = b"x" * (small_limit + 1)
    view._on_output(big)
    # The drain ran inline: nothing pending, buffer empty, all bytes parsed.
    assert not scheduled
    assert not view._output_buffer
    assert _text(view.emulator).startswith("x" * 64)
    # A following small chunk schedules normally again.
    view._on_output(b"\r\nafter")
    assert len(scheduled) == 1
    scheduled[0]()
    assert "after" in _text(view.emulator)
```

**理由**：测试目的是验证 overflow 时的 drain 逻辑，不是验证 1MB 精确值；
1025 字节已足够触发 overflow 分支（`len(buffer) > 1024`），且断言的等价形式保留。
`x` 字符无副作用（不会触发特殊 VT 序列），断言 `_text(view.emulator).startswith("x" * 64)`
在新尺寸下依然成立。

**预计提速**：9.10s → ≈ 0.01s（900x）。

### 3.3 `test_pack_wiki.py::test_stale_is_reported_then_retranslated`（9.42s）

**根因**：测试调用 `wiki.run` 3 次（test_pack_wiki.py:199-230），每次都对
`repo` fixture 的 10-15 个页面执行 lint  pass。`_get_lint_engine` 虽缓存
（tools/pack/wiki.py:255 `@functools.cache`），但首次调用需导入 `pymarkdownlnt`
并构造 `LintEngine`（tools/pack/wiki.py:270-272），耗时约 3-5s；后续 2 次 `wiki.run`
复用缓存引擎，但仍需对每页执行 `engine.fix(text)`（tools/pack/wiki.py:304），
10-15 页 × 3 次 run × 每页 lint 耗时 ≈ 0.2s = 6-9s。翻译 stub 已是 Python 函数
（test_pack_wiki.py:202-205, 211-214, 220-224 monkeypatch `translate_via_cmd`），
无子进程开销。

**调研结论**：翻译已 stub，瓶颈在 lint 引擎初始化与每页 lint。提速方案有二：
1. **减少页面数**：创建专用 fixture 替代 `repo`，只保留 3-4 个页面（1 个 plan、
  1 个 review、1 个 bilingual twin、1 个 orphan），将 lint 耗时降至 1/3；
  但需验证测试逻辑仍成立（stale 检测、retranslation、manifest 更新）。
2. **mock lint 引擎**：monkeypatch `_get_lint_engine` 返回一个 no-op stub
  （`fix(text) -> text`），跳过 pymarkdownlnt 导入与 lint  pass。测试验证的是
  stale 检测与 retranslation 逻辑，不依赖 lint 修复，mock 不影响语义。

**选定方案**：方案 2（mock lint 引擎）。理由：方案 1 需改 fixture，影响同文件
其他用例（test_pack_wiki.py 共 20+ 用例共用 `repo` fixture）；方案 2 只改本用例，
隔离性好，且 lint 非本测试验证目标。

**改动位置**：[test_pack_wiki.py:199-230](file:///D:/Programming/yate-test-speedup/tests/test_pack_wiki.py#L199-L230)

```python
# 新增 stub（在 test_stale_is_reported_then_retranslated 函数开头）
def test_stale_is_reported_then_retranslated(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Mock the lint engine to skip pymarkdownlnt import and per-page lint.
    # This test verifies stale detection and retranslation, not lint fixes.
    class _NoOpEngine:
        def fix(self, text: str) -> tuple[str, list]:
            return text, []
    monkeypatch.setattr(wiki, "_get_lint_engine", lambda lang: _NoOpEngine())
    
    def v1_translate(text: str, translate_cmd: str) -> str | None:
        return "# orphan en v1\n"
    # ... 其余代码不变
```

**预计提速**：9.42s → ≈ 0.5s（19x，跳过 lint 引擎初始化与 3 轮 × 10-15 页 lint）。

### 3.4 `test_release_tool.py` 两个用例（9.12s + 8.91s）

**根因**：两个用例均为集成测试，验证 release tool 与真实 git 仓库的交互。
每个用例调用 `_seed_origin_and_clone`（test_release_tool.py:197-206）创建
bare origin + work clone，涉及 `git init` / `git config` (2x) / `git add` /
`git commit` / `git clone --bare` / `git clone` / `git config` (2x)，共 9 次
git 子进程；`test_release_refuses_when_tag_exists_on_origin` 额外调用
`_clone_upstream`（test_release_tool.py:209-215）创建第二个 clone（3 次 git），
再执行 `git tag` / `git push`（2 次 git）。两个用例共约 25 次 git 子进程调用，
每次 ≈ 0.3-0.5s（Windows 下 git 启动开销），合计 ≈ 8-12s。

**调研结论**：git 子进程属合理集成成本、无可安全削减项。理由：
1. **测试目标是 git 交互**：release tool 的核心逻辑是验证分支状态、tag 冲突、
  rollback 等 git 语义，mock git 将失去集成测试价值；
2. **git 调用不可精简**：每个 git 命令验证一个独立语义（init 建仓、clone 验证远程、
  tag 验证冲突、push 验证同步），删除任一调用将破坏测试覆盖；
3. **session 级模板仓收益有限**：可创建 session-scoped fixture 缓存模板 repo，
  用 `git clone --local`（硬链接）替代每次 `git init` + `git commit`，但实测
  Windows 下 `git clone --local` 仍需 0.5-1s（含对象库拷贝），且需重构
  `_seed_origin_and_clone` / `_clone_upstream` / `_point_release_at` 三个 helper，
  影响 test_release_tool.py 全部 15+ 用例，改动面大、收益小（预计提速 ≤ 2x）；
4. **pytest-xdist 已并行**：两个用例在不同 worker 并行执行，单用例耗时即墙钟耗时，
  无进一步并行空间。

**选定方案**：从提速清单移除，保留原耗时。理由：git 子进程是集成测试的合理成本，
mock 或精简将破坏测试语义；session 级模板仓改动面大、收益小，不纳入本轮提速。

**预计提速**：无（9.12s + 8.91s 维持不变，属合理集成成本）。

## 四、实施步骤

### 步骤 1：修改 `test_ts_backend.py`

**改动文件**：`tests/test_ts_backend.py`

**改动内容**：按 §3.1 将步数从 20000 降至 5000（test_ts_backend.py:1181）。

### 步骤 2：修改 `test_terminal.py`

**改动文件**：`tests/test_terminal.py`

**改动内容**：按 §3.2 用 `monkeypatch.setattr` 将 `OUTPUT_BUFFER_LIMIT` 改为 1024，
测试喂 1025 字节（test_terminal.py:628-643）。

### 步骤 3：修改 `test_pack_wiki.py`

**改动文件**：`tests/test_pack_wiki.py`

**改动内容**：按 §3.3 在 `test_stale_is_reported_then_retranslated` 函数开头
mock `_get_lint_engine` 返回 no-op stub（test_pack_wiki.py:199-230）。

### 步骤 4：不修改 `test_release_tool.py`

**改动文件**：无

**改动内容**：按 §3.4 调研结论，git 子进程属合理集成成本，两个 release tool 用例
从提速清单移除，保留原耗时。

## 五、新增测试

无新增测试（本次只优化现有测试）。

## 六、验证方案

### 验证目标

证明提速后的测试仍保留原有语义，且耗时显著降低。

### 验证命令

```powershell
# 1. 单用例验证（确保语义未变）
.venv\Scripts\python.exe -m pytest tests/test_ts_backend.py::test_incremental_matches_full_reparse_over_random_edits -v
.venv\Scripts\python.exe -m pytest tests/test_terminal.py::test_output_buffer_overflow_drains_synchronously_without_loss -v
.venv\Scripts\python.exe -m pytest tests/test_pack_wiki.py::test_stale_is_reported_then_retranslated -v
.venv\Scripts\python.exe -m pytest tests/test_release_tool.py::test_release_rolls_back_when_version_tests_fail -v
.venv\Scripts\python.exe -m pytest tests/test_release_tool.py::test_release_refuses_when_tag_exists_on_origin -v

# 2. 耗时对比（提速效果）
.venv\Scripts\python.exe -m pytest tests/ --durations=10 -q -n auto

# 3. 全量验证（确保无回归）
.venv\Scripts\python.exe -m pytest tests/ -q -n auto

# 4. 架构守卫
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q

# 5. pyright
.venv\Scripts\python.exe -m pyright tests/
```

### 通过判定

- 所有修改的用例通过（退出码 0）；
- Top-3 可提速测试总耗时从 ≈ 33s（14.67s + 9.10s + 9.42s）降至 ≤ 5s（3.7s + 0.01s + 0.5s）；
- Top-5 总耗时从 ≈ 52s 降至 ≈ 24s（含 release tool 两用例 18s 维持不变）；
- 全量 pytest 全绿；
- 架构守卫 37 项全绿；
- pyright 零诊断。

## 七、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 提速后测试失去防护 | 保留原断言的等价形式 | `git revert` 对应文件的改动 |
| 步数/ buffer 减少暴露新 bug | 发现 bug 立即修复或登记 issue | 测试本身不回滚，bug 另案处理 |

## 八、独占文件清单

- `tests/test_ts_backend.py`
- `tests/test_terminal.py`
- `tests/test_pack_wiki.py`
- `tests/test_release_tool.py`

## 九、预计影响

- **测试时长**：Top-5 总耗时从 ≈ 52s 降至 ≈ 24s（Top-3 可提速测试从 33s 降至 5s，
  release tool 两用例 18s 维持不变属合理集成成本）；
- **覆盖率**：不影响（未删除测试）；
- **可信度**：测试语义保留，防护能力不降。

## 十、修订记录（第 2 轮）

**修订日期**：2026-10-31

**修订内容**：

1. **§3.1**：步数从 20000→2000 改为 20000→5000，论证 5000 步对 `_mutate` 七类编辑形态
   （字符插删/行插删/整行替换/跳段替换/undo）的覆盖充分性（每类 ≈714 次）；
   预计提速从 10x 调整为 4x（14.67s → 3.7s）。

2. **§3.2**：修正语义错误——原方案"喂 `OUTPUT_BUFFER_LIMIT // 10 + 1`（约 100KB）"
   不会触发 overflow 分支（阈值 1MB）。改为 `monkeypatch.setattr` 将
   `yate.editor_view.terminal.OUTPUT_BUFFER_LIMIT` 改为 1024，测试喂 1025 字节。
   核实结论：`OUTPUT_BUFFER_LIMIT` 是模块级常量（terminal.py:79），在 `_on_output`
   中运行时读取（terminal.py:207），monkeypatch 模块属性即可生效。
   预计提速从 10x 提升至 900x（9.10s → 0.01s）。

3. **§3.3**：消除"待调研"空泛表述。实测调研结论：翻译已 stub（monkeypatch
   `translate_via_cmd`），瓶颈在 lint 引擎初始化（首次导入 pymarkdownlnt）与
   3 轮 × 10-15 页 lint。选定方案：mock `_get_lint_engine` 返回 no-op stub，
   跳过 lint pass。预计提速 19x（9.42s → 0.5s）。

4. **§3.4**：消除"待调研"空泛表述。实测调研结论：git 子进程属合理集成成本、
   无可安全削减项。理由：测试目标是 git 交互（分支状态/tag 冲突/rollback），
   mock git 将失去集成测试价值；每个 git 命令验证独立语义，不可精简；
   session 级模板仓改动面大、收益小（≤ 2x）。**从提速清单移除**，保留原耗时
   （9.12s + 8.91s = 18s 维持不变）。

5. **§四 实施步骤**：移除"调研"字样，改为具体改动位置与内容。

6. **§六 通过判定**：更新目标数字——Top-3 可提速测试从 33s 降至 ≤ 5s，
   Top-5 总耗时从 52s 降至 ≈ 24s（含 release tool 18s 维持不变）。

7. **§九 预计影响**：同步更新耗时数字。
