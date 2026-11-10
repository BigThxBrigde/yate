# IKTRDV 合并前 pr-review 修复方案（review-fixes）

> 来源记录：[`../reviews/2026-11-10-pr-review-feature-feat-pack-dist-zip.md`](../reviews/2026-11-10-pr-review-feature-feat-pack-dist-zip.md)
> （`pr-review` skill `review` 模式，范围 `master...HEAD`）。唯一规范来源：本文件 +
> 来源记录 + `.trae/rules/` 8 份必读规则 + `.trae/skills/pr-review/SKILL.md`。
> 本文引用仓库文件的相对路径以 `.trae/documents/` 为基准；代码块内命令相对基准是
> 仓库根。无人值守下【批准】按通过处理，不冒充用户确认。

## 1. 目标与非目标

**目标**：把 pr-review 发现的 1 条 MAJOR（`--stage` 畸形名导致 arcname `/` / `../`
与越界 `rglob`）与两条合并阻碍（评审索引编号重复、`README.md` 索引真实冲突块）
修至归零，达到 `APPROVE`（0 BLOCKER / 0 MAJOR，仅 minor 待办）；七道硬门禁
在修复后重跑并保持全绿；`git merge-tree` 冲突块归零。

**非目标**：
- 不改三脚本 `--dist` 既有语义、不加 `--zip` 正向开关、不改 PyInstaller spec；
- 不修评审已登记的 minor（非 ASCII stage 名、0600 产物权限、并发交错、守卫
  顺序、symlink 边界独立性、N2–N5、m1/m7、存量 `test_app_panes` 竞态），一律
  登记待办；
- 不自动合并 master、不推送、不改 CHANGELOG（`chore(changelog)` 属 master 侧
  发布流程）；
- 不篡改历史评审记录里的「架构 37」等时点事实数字，只在 pr-review 记录里
  登记合并后应为 38。

## 2. 备选方案与否决理由

| 方案 | 内容 | 裁决 |
| --- | --- | --- |
| A（选中） | `archive_stage` 入口 `resolved = stage.resolve()`；拒绝原始 `stage.name` 为空 / `.` / `..`；`stage_name = resolved.name` 显式传给 `_stage_files` / `_write_archive`；`_stage_files` 跳过符号链接并断言每个条目 `resolve().is_relative_to(root)` | 选中：一次性封住 `/` 与 `../` arcname、越界遍历与 symlink 跟随，改动局限在新增助手，脚本调用路径（stage 名固定 `yate-<ver>-<os>-<arch>`）零行为变化 |
| B | 只在模块 docstring / 帮助里声明「不要给 `--stage` 传 `.` 或 `..`」 | **否决**：不消除越界读取与危险归档内容，仅把风险转嫁给调用者，不符合 issue §二.3 / §二.5 |
| C | 改用 `zipfile.ZipInfo.from_file()` 让 stdlib 推导 arcname 与 mode | **否决**：`from_file` 只处理单条目，不会阻止 `rglob("*")` 遍历 `.git/` / `.venv/`；且 Windows 上 `create_system` / mode 语义与本轮显式 `external_attr` 契约冲突 |
| D（选中，合并阻碍） | 索引编号顺延为 #73（IKTRDV 两轮评审）/ #74（本次 pr-review），并把本分支增量段移到不与 master 插入点（#69 段之后）重叠的位置 | 选中：编号唯一 + hunk 错开，合并冲突可验证归零 |
| E | 保留 #70 与现有位置，合并时人工解决冲突 | **否决**：无人值守下不得把可低成本消除的合并阻碍留给人类；且编号重复会让索引不可信 |

## 3. 分步实施（波内文件不重叠）

| wave | 子计划 | 独占文件 | 输出 |
| --- | --- | --- | --- |
| P1 | a | `../../tools/pack/zip_dist.py`、`../../tests/test_pack_zip.py` | MAJOR 修复 + 3 个回归用例 |
| P1 | b | `../../.trae/reviews/README.md`、`../../.trae/documents/pack-dist-zip-progress.md` | 编号顺延 + 增量段移位 + 状态回填 |
| P2 | 主代理 | 来源评审记录、本方案 | 门禁回填、verdict、互链、提交 |

## 4. 详细修改与验收命令

### 4.1 P1-a：`tools/pack/zip_dist.py` + `tests/test_pack_zip.py`

1. `archive_stage(stage, dist_root, *, posix=None)` 入口（现 `:163-170`）：
   ```python
   raw_name = stage.name
   if not raw_name or raw_name in {".", ".."}:
       raise ZipDistError(f"invalid stage directory name: {stage!r}")
   root = stage.resolve()
   stage_name = root.name
   ```
   用 `root` 替换后续 `stage.rglob` / `relative_to` 的基准；`archive` 产物名与
   `mkstemp` prefix 改用 `stage_name`（与 arcname 顶层目录同源）。
2. `_stage_files(stage: Path) -> list[tuple[Path, str]]` 改为
   `_stage_files(root: Path, stage_name: str) -> list[tuple[Path, str]]`：
   循环内 `if path.is_symlink() or not path.is_file() or path.name in _TEMP_NAMES:
   continue`；`real = path.resolve()`；`if not real.is_relative_to(root): raise
   ZipDistError(f"stage entry escapes stage root: {path}")`；arcname =
   `f"{stage_name}/{path.relative_to(root).as_posix()}"`。docstring 用英文说明
   symlink 跳过与越界拒绝（symlink 是 MINOR 面，随同一处收口，不单列修复）。
3. `_write_archive(target, entries, *, posix)` 增加显式参数
   `stage_name: str`，删除 `entries[0][1].split("/", 1)[0]` 的反向推导。
4. `tests/test_pack_zip.py` 新增 3 个用例（arrange / act / assert）：
   - `test_archive_stage_when_stage_is_dot_raises_zip_dist_error`：arrange
     `Path(".")` 与 `tmp_path`；act `archive_stage(Path("."), tmp_path)`；assert
     `pytest.raises(ZipDistError, match="invalid stage directory name")` 且
     `tmp_path` 下无 zip / tmp 产物（证明未遍历 cwd）。
   - `test_archive_stage_when_stage_is_parent_segment_raises_zip_dist_error`：
     arrange `(tmp_path / "release" / "..")`；act 同上；assert 同样异常。
   - `test_archive_stage_when_stage_name_is_resolved_top_level_prefix`：arrange
     正常 stage fixture；act 归档；assert 所有 `namelist()` 以
     `f"{stage.resolve().name}/"` 开头、无条目以 `/` 开头或含 `../`。
   既有 14 个用例断言不变（fixture stage 名合法）。

**验收命令**：
```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_zip.py tests/test_pack_spec.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

### 4.2 P1-b：评审索引与进度文档

1. `.trae/reviews/README.md`：把本分支的「**2026-11-10 IKTRDV 增量**：新增 #70」
   整段改为「新增 #73」，并把该段**移出** master 的插入点（#69 增量段之后、
   `> **编号分歧登记**` 之前）到不与 master hunk 重叠的位置（`#68`/`#69`
   增量段之前，即散文增量区更早处；以 `git merge-tree` 实测零冲突为准）。
   本次 pr-review 记录另登记 #74（落盘评审记录时一并写入）。
2. `.trae/documents/pack-dist-zip-progress.md` 追加「合并前 pr-review 轮」章节，
   登记范围、基线漂移（master `18e96d2a`、架构 38）、子代理零产出、修复与
   复评结论。

**验收命令**：
```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_spec.py -q
.venv\Scripts\python.exe -m tools.changelog check
git merge-tree <merge-base> master HEAD   # 用 Python 解析 CONFLICT_MARKERS == 0
```

### 4.3 P2：主代理复评与提交

- 回填来源评审记录（verdict + 门禁实测 + 修复闭环 + minor 待办）与本方案；
- 单笔提交（修复 + 文档 + 评审记录 + 方案），只提交不推送、不自动合流；
- 工作树干净；`git status --short` 为空。

## 5. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| `resolve()` 改变 stage 基准，导致真实构建产物 zip 内容变化 | 三脚本传的是绝对路径且不含 `..`；wave-4 产物形态由新增用例与 E2E 记录背书；修复后重跑真实 `--dist` 一次（可选） | `git revert` 修复提交 |
| 跳过 symlink 让含链接的 Linux stage 少文件 | Linux 产物由 `cp -a` 复制，符号链接罕见；docstring 显式声明；登记为 minor 观察 | 改为抛错或写 symlink 条目 |
| 增量段移位后仍与 master 冲突 | 以 `git merge-tree` 的 `CONFLICT_MARKERS` 实测为判据，不为零继续调整位置 | 继续移位 |
| 编号顺延与 master 未来编号再撞 | 采用当前 master 最大编号 +1（#73/#74）并在评审记录注明合并时按日期统一重排 | 合并时人工重排 |

## 6. 验收判据

- `APPROVE`：0 BLOCKER / 0 MAJOR；MAJOR（zip slip）有回归用例且实测通过；
  合并冲突块归零；七道门禁（pyright / pytest -n auto / 架构 37（合并后 38）/
  覆盖率 ≥75 / 冒烟 / changelog / diffcheck）实测全 0；
  评审索引编号唯一、增量段不冲突；评审记录与方案双向互链；工作树干净。
- minor 全部登记待办，不阻塞合入（合并决定仍由人类作出，见 skill Step 4）。

## 7. 执行结果（P1/P2 回填）

- P1-a（`tools/pack/zip_dist.py` +13 行、`tests/test_pack_zip.py` +25 行）：
  入口拒绝空 / `.` / `..` 名、`root = stage.resolve()`、`stage_name = root.name`
  贯穿产物名 / mkstemp prefix / arcname；`_stage_files` 跳过 symlink 并断言
  `is_relative_to(root)`；`_write_archive` 接收显式 `stage_name`；3 个回归
  用例落地。主代理复核 49 passed / pyright 0 / 架构 37。
- P1-b（`.trae/reviews/README.md`）：IKTRDV 增量段改为 #73 并移到 #67 段之前；
  提交 `6f842d34` 后主代理用提交态 `git merge-tree` 独立复核：
  `CONFLICT_MARKERS 0`、`CHANGED_IN_BOTH 3`、`IDX_70 0` / `IDX_73 1` /
  `IKTRDV_SEGMENTS 1`。P1-b 因未提交态探针不可见而用临时 index + write-tree
  等价探测，已登记偏差并由提交态复核闭环。
- 主代理兜底（分域 B/C）：六维度结论、行宽 100 实测 `OVER100 []`、本轮文档
  2 处本机绝对路径脱敏、提交规范与 diffcheck 0，全部写入评审记录 §三。
- 修复后七道门禁 `GATE_RCS [0,0,0,0,0,0,0]`（覆盖率 92.95% /
  3498 passed·10 skipped）；首轮覆盖率红经 `-n 1` 复核为 safe-delete 环境钩子
  （`count=18852 > 9999`），非产品缺陷。
- 探针口径订正：收尾复核的裸冲突起始标记计数因评审记录正文引用该标记文本
  而误报 1；精确判据（冲突块起始 `.our` / 结束 `.their` 标记计数）实测 0，
  非真实冲突回归，已在评审记录 §二与进度文档登记。
- 结论：评审记录 `2026-11-10-pr-review-feature-feat-pack-dist-zip.md` 给出
  **APPROVE**（0 BLOCKER / 0 MAJOR / 7 MINOR 待办）；索引登记 #73 / #74；
  未推送、未合流、工作树干净。
