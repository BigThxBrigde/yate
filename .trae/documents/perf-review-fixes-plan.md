# perf 分支 pre-review 修复方案（perf-review-fixes）

来源评审记录：[2026-10-12-perf-profiling.md](../reviews/2026-10-12-perf-profiling.md)
（enh/perf-profiling 分支 pre-review，APPROVE，2 MINOR）。用户指令
「记录，执行闭环流程修复」= 本轮修复的批准（承接 perf 任务「无人值守」预授权，
不再等待确认，记为偏离）。

## 一、目标与非目标

**目标**

1. M1：`cell_width` 记忆缓存有界化——消除无上界模块字典，且渲染热路径
   性能不回退（以探针数据选型）。
2. M2：`palette.refilter` 恢复 `elif` 平铺读感（行为零变化，parity 测试锁定）。

**非目标**

- 不改 `fuzzy_match` / `_match_lowered` 公共行为与签名；
- 不动 `cell_offsets` / 渲染路径算法结构；
- 不新增「防病理输入」之外的防御逻辑。

## 二、备选方案与否决理由

### M1 选型（探针定夺，三条候选）

| 候选 | 说明 | 预判 |
|---|---|---|
| A. `functools.lru_cache(maxsize=…)` | PEP 惯用有界缓存，删手写字典 | 命中路径比裸 dict 略慢（C lru_cache 开销），需实测 |
| B. 有界字典 + 溢出清空 | 保留 dict 命中速度，`len >= MAX` 时 `clear()` 回填哨兵 | 3 行改动、零新依赖；thrash 时退化为无缓存基线 |
| C. 维持现状（仅文档声明） | 评审自评信息级 | 用户已指令修复，否决 |

实现取探针更优者（A 优先——惯用且删代码；命中开销超出 A 基线 15% 以上才落 B）。

### M2

恢复原 `elif` 链形态（`if match … elif commands_mode and hint … else: continue`），
与预降级镜像共存。否决「还原回每次 `str.lower()`」：将回退 IKKSHY 实测 2× 收益。

## 三、分步实施

| 步 | 改动文件 | 内容 | 验收 |
|---|---|---|---|
| 1 | `.trae/reviews/2026-10-12-perf-profiling.md`、`.trae/documents/perf-review-fixes-plan.md`、`.trae/reviews/README.md` | 记录 + 方案落盘，索引登记（速览 #41 + 轮次总表） | `git commit docs` |
| 2 | 临时探针（%TEMP%，用后删） | M1 三候选命中路径 ns/char 实测 | 数据选型 |
| 3 | `yate/editor_view/cells.py` | M1 按选型落地 | 探针复测无回退 + `pytest tests/test_app_render.py -q` |
| 4 | `yate/editor_view/palette.py` | M2 elif 链恢复 | `pytest tests/test_app_explorer.py tests/test_app_palette.py -q` |
| 5 | 全量门禁 | pyright / pytest 全量 / 探针复测 | 退出码 0 |
| 6 | 收尾 | 计划回填 + README 状态翻 ✅ + perf-profiling-plan 的 MINOR 登记行改指向 | `git commit docs` |

## 四、风险与回滚

- M1 若选 lru_cache：行为纯等价（纯函数记忆化），唯一风险是命中开销，
  由探针前置否决；若选有界字典：thrash 场景退化为无缓存基线（即优化前状态），
  可接受。
- M2 纯结构重排，parity 测试 + palette 回归双重锁定。
- 回滚：各步独立提交，`git revert` 单笔即可。

（本方案为局部缓存策略与代码形态调整，不涉及业务流程 / 架构 / 模块交互，
按 plan-before-execute §二不配 Mermaid 图。）

## 五、执行结果回填（2026-10-12）

（执行后回填）
