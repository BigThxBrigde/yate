# wave-1 / plan-b：双语文档与示例说明同步

- 总纲：[overview.md](overview.md)；主计划：[../which-key-auto-trigger-plan.md](../which-key-auto-trigger-plan.md)
- 需求来源：[../which-key-auto-trigger-issue.md](../which-key-auto-trigger-issue.md)（§四边界、§六需同步的文档）
- 同波并行：`plan-a`（配置代码），文件互不重叠（`yate/yaterc.example` 归 plan-a，本计划不碰）
- 进入条件：方案批准；退出条件：本文件 §五检查退出码 0

## 一、输入

- 主计划 §二文档事实、§七范围裁决（CHANGELOG 生成式不手改、README 只核对、manual 补 `:set` 命令表）。
- 既有文本：`yate/docs/yaterc.en.md:81,105-107` ↔ `yate/docs/yaterc.zh.md:73,94-95`；`yate/docs/which-key.en.md:11,19-31` ↔ `which-key.zh.md:9,18-28`；`FEATURES.md:30-31,82-83,89-91,205` ↔ `FEATURES.zh.md:24,67,74,168`；`yate/resources/manual.en.md:806-820`（zh 对应 `:set` 命令表）；`README.md:261-262,292-294` ↔ `README.zh.md:277-278,308-310`。

## 二、独占文件清单（只改这些）

1. `yate/docs/which-key.en.md`
2. `yate/docs/which-key.zh.md`
3. `yate/docs/yaterc.en.md`
4. `yate/docs/yaterc.zh.md`
5. `yate/resources/manual.en.md`
6. `yate/resources/manual.zh.md`
7. `FEATURES.md`
8. `FEATURES.zh.md`
9. `README.md`
10. `README.zh.md`

**显式不改**：`CHANGELOG*.md`、`yate/resources/changelog.*.md`、`yate/yaterc.example`（plan-a 独占）、任何 `.py` / 规则 / 计划文档。

## 三、具体修改（逐文件、成对同步）

1. `yate/docs/yaterc.en.md:81` / `yaterc.zh.md:73` — 选项表在 `which_key` 行后新增 `which_key_auto` 行：`bool` / 默认 `True` / `True | False` / 说明「只控制挂起前缀与 `ctrl+w` 和弦的自动弹出；`False` 时 `<f9>` 手动钉住仍可用；`which_key=False` 优先且隐藏一切；非布尔值被拒绝」。中英各自表述，不作机翻式直译。
2. `yate/docs/yaterc.en.md:105-107` / `yaterc.zh.md:94-95` — 作用范围段补一句：`which_key_auto` 由 `WhichKeyFlows.refresh()` 每次读取（不进入 `toggle()`），`:set which_key_auto=off|on` 即时生效；总开关优先级说明。
3. `yate/docs/which-key.en.md:11,19-31` / `which-key.zh.md:9,18-28` — 在概述处补充「两种读法可分别配置」：`which_key = False` 的既有描述保持不变（§四硬约束），另补 `which_key_auto = False` 只关闭自动弹出、F9 钉住仍可用、钉住期间不受前缀态影响；四分支优先级说明中插入 auto 闸门位置（pinned 之后）。不得改动触发时机描述（仍为每键同步）。
4. `yate/resources/manual.en.md:806-820` / `manual.zh.md` 对应 `:set` 命令表 — 新增两行：`:set which_key=<bool>`（总开关）与 `:set which_key_auto=<bool>`（仅自动触发，F9 仍可用）。既有手册无 `which` 字面（实测 0 命中），不新开章节、不改其它段落。
5. `FEATURES.md:30-31` / `FEATURES.zh.md:24` — which-key 功能描述补「自动触发可独立关闭」；`:82-83` / zh `:67` 的 `:set` 运行时选项清单追加 `which_key_auto`；`:89-91` / zh `:74` 的 Full option set 追加 `which_key_auto`；`:205` / zh `:168` 的 yaterc 选项列表追加 `which_key_auto`。四处清单按既有排版（反引号包裹、斜杠分隔）保持双语行数 / 顺序对应。
6. `README.md` / `README.zh.md` — **核对**功能清单与 `which-key` 双语页索引中是否存在 which-key 开关条目；实测无开关描述则**不新增条目**，在报告中登记核对结论（issue 措辞为「涉及 which-key 开关的条目」，不存在即无须改动）。若发现遗漏的开关描述，则按同一语义双语同步补一句，并回填说明。
7. `CHANGELOG*.md` — 按主计划 §七裁决不手改；新条目随规范英文提交信息进入 `[Unreleased]`，收尾由主代理跑 `python -m tools.changelog check` 并回填。

## 四、输出

- 六份核心手册 / 文档双语成对含 `which_key_auto` 且语义一致；FEATURES 双语四处清单同步；示例配置由 plan-a 负责。
- 不改变 `which_key=False` 的既有陈述（面板彻底不显示、F9 no-op），只补优先级关系。
- 文档内不出现本机绝对路径；新增引用使用仓库内相对路径（`doc-conventions.md` §五）。

## 五、可执行验收命令（worktree cwd，PowerShell）

```powershell
.venv\Scripts\python.exe -c "from pathlib import Path; names=['yate/docs/which-key.en.md','yate/docs/which-key.zh.md','yate/docs/yaterc.en.md','yate/docs/yaterc.zh.md','yate/resources/manual.en.md','yate/resources/manual.zh.md','FEATURES.md','FEATURES.zh.md']; missing=[n for n in names if 'which_key_auto' not in Path(n).read_text(encoding='utf-8')]; print('missing:', missing); raise SystemExit(1 if missing else 0)"
git diff --check
```

判据：两条退出码 0；`missing: []`。纯文档变更按 `misc-rules.md` §三可豁免运行测试，但本波与 plan-a 构成混合变更，全量门禁仍由主代理收尾执行，不得据此豁免整体门禁。

## 六、风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 中英不对齐 / 只改一侧 | §五命令对 8 个文件逐一检查关键词，四组清单一并核对 | 回退本计划文档提交 |
| 误改 `which_key=False` 既有语义 | 只增补、不改写原句 | 回退对应段落 |
| 手改生成式 changelog 导致 CI released-section drift | 明确不改；收尾 `check` 验证 | 无需回滚（本就不改） |
| README 虚构条目 | 先核对再决定，结论写进报告 | 回退 README 改动 |

## 七、报告格式

改动清单（文件 + 段落定位）、实际命令与退出码、README 核对结论、未解决项。偏离须显式列出并给依据（尤其若 README 需补条目）。
