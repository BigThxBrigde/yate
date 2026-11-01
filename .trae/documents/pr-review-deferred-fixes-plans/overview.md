# pr-review 另案修复波总纲 — feat/file-manager（2026-11-01）

**来源**：`.trae/reviews/2026-11-01-pr-review-feat-file-manager.md` §一 m5 / m8 / m9 / m10
（先读对应小节全文）。处置档位：合并前「Can be deferred」五条中的四条；
**m11 不在本波**（按评审裁决并入「中栏万级条目增量刷新」立项，另行出方案）。

**批准方式**：用户 2026-11-01 明示「无人值守、无须过问」——方案落盘即视为批准，
不再走 NotifyUser 审批（偏离 plan-before-execute §二.3，依据用户指令豁免，
收尾汇报显式登记）。方案由主代理按 plan-architect-designer 剧本兜底产出
（该角色模型本机 spawn 未注册，历史两次实证，见项目记忆）。

## 子计划与文件互斥

| 子计划 | 修的条目 | 独占文件 |
|---|---|---|
| [fix-preview.md](fix-preview.md) | m5、m9 | `yate/editor_view/preview.py`、`yate/editor_view/palette.py`、`yate/editor_view/filemgr.py`、`tests/test_palette_preview.py` |
| [fix-editor.md](fix-editor.md) | m8 | `yate/editor.py` |
| [fix-navtest.md](fix-navtest.md) | m10 | `tests/test_filemgr.py`、`yate/editor_view/filemgr_keys.py`（见下方偏离记录） |

三批文件集互不重叠。执行波次：

- **Wave 1（并行 2 批）**：fix-preview ∥ fix-editor；
- **Wave 2（串行 1 批）**：fix-navtest——必须在 Wave 1 全部落盘后执行，
  其 pilot 用例要跑在 m5/m9 改动后的 `filemgr.py` 上。

**偏离记录（Wave 2，主代理裁决）**：m10 新用例先红命中真实产品缺陷——
`filemgr_keys.py` 的 `nav(...)` 绑定裸参数无法被 Textual 解析，六键真实派发失败；
主代理亲自修复该产品源码（参数加引号），文件归入 fix-navtest 批名下。
证据链见 fix-navtest.md「执行偏离记录」。

禁止触碰上表之外的任何文件（评审记录本身不修改）。跑测试不受独占限制，
改文件受。

## 硬约束

1. pyright strict **零诊断**；完整类型注解 + docstring；禁 `Any` / `Protocol` /
   `TYPE_CHECKING`；禁相对导入；回调别名用 PEP 695 `type` 语句。
2. 代码注释、docstring 一律英文（misc-rules §四），行宽 ≤100。
3. 架构边界不动：不新增跨层导入；`preview.py` 保持「consumer screens import
   本模块、反向禁止」的单向导入；两屏不新增任何 `editor` / `app` 依赖。
4. 行为等价纪律：m5 是纯抽取（装配结果逐字节一致），m9 是守卫替换（卸载后
   worker 本就被 `workers.cancel_node` 取消，`is_attached` 只是让守卫真实生效），
   m8 是派发路由对齐（动作注册体须先核实确实路由到 `open_overlay`）。
   三条均**不适用先红后绿**（非缺陷修复、非行为变更）；m10 是补覆盖，同样
   不适用。
5. 每批自测命令见各自子计划；按退出码判定（本机 `pytest -q` 无汇总行）。
6. 完成后**不提交**，汇报：改动文件、diff 要点、自测命令与退出码、未解决项。

## 评审与收尾（2026-11-01，主代理记录）

- **执行**：Wave 1 fix-preview ∥ fix-editor、Wave 2 fix-navtest 均落盘，主代理
  独立复核通过（文件范围与独占清单一致、pyright 0、关联用例全绿）。
- **收口评审**（reviewer-deferred / code-review-expert）：1 blocker / 0 major /
  3 minor——blocker 为 m10 新用例 docstring 的 `right/left/home/end/...` 连写
  形成 `/home/end` 子串命中家目录路径守卫（`test_no_machine_local_home_paths_
  in_sources` 红，架构门禁阻塞）；按规则「新增命中不得登记豁免、须改写文本」
  改写为首行无斜杠连写表述。m1（m9 守卫分支不可达，docstring 注明防御性冗余）、
  m2（preview.py 模块 docstring 对齐 `preview_text` 职责）、m3
  （test_preview_truncates_large_file docstring 对齐并恢复面板级截断断言）
  已随手修复。评审其余各面（m5 逐字节等价、m8 路由、m9 语义、filemgr_keys
  修复完整性、架构边界、方案一致性）全部明确通过。
- **修复后主代理全量门禁五项全绿**：pyright 0 诊断 / pytest 3313 passed·
  10 skipped / 架构 37 / 覆盖率 92.82%（阈值 75）/ 冒烟 121 场景·1463 checks。
- **遗留登记（另案）**：同类 `is_mounted` 死守卫在 `manual.py`（5 处）、
  `highlighting.py`（2 处）、`find_replace.py`（2 处）仍有 9 处，建议统一收敛
  （m9 同法处理）；m11 维持并入「中栏万级条目增量刷新」立项。
