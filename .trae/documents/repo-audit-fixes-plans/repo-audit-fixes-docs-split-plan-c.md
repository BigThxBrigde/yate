# 子计划 plan-h：用户文档分工成文（A16）

> 所属波次：**wave-3**（与 flows-package-plan-c 文件不重叠，可并行；主代理执行——文件在 `yate/` 包内）。
> 来源：评审 A16。

## 一、输入

- 两处堆放点：`yate/docs/`（4 主题 × 双语：extensions / lsp / themes / yaterc，站外阅读）与 `yate/resources/manual.en.md`（75.32 KB）/ `manual.zh.md`（72.32 KB）（应用内渲染，随 wheel 分发，pyproject:163 注释确认打进包）；
- 重叠实例：`resources/manual.zh.md:932-947` 与 `docs/themes.zh.md:96-120` 各讲一遍主题模板用法；
- 约束：manual 是应用内**离线阅读**硬需求，不能删减为链接；双语成对是硬约束（doc-conventions §三）。

## 二、独占文件清单

1. `yate/docs/README.md`（新增，会随 hatchling 进 wheel——内容写成面向"源码树读者"的双语简注，无害）
2. `yate/docs/themes.en.md` / `themes.zh.md`（主题模板章节头部加来源声明，内容不改写）
3. `yate/resources/manual.en.md` / `manual.zh.md`（主题模板章节头部加来源声明，内容不改写）

## 三、具体修改

分工定案（单一权威声明，不合并内容）：
- `yate/docs/` = **站外阅读权威**（GitHub/Gitee 渲染、外链可达）；
- `yate/resources/manual.*.md` = **应用内权威**（`:help` 手册渲染，离线可用，随版本打包）；
- 主题模板章节允许两处共存（离线需求），但各加一行来源声明互相指认，消除"重叠无人认领"。

具体落点：
1. `docs/README.md`：双语（同文件两节）说明上表分工 + 四主题清单 + "应用内请用 `:help` 阅读 manual"；
2. `docs/themes.*.md` 主题模板章节（en :96 附近 / zh :96-120）头部插入引用块：
   > 应用内离线版本见 `:help` 手册（`yate/resources/manual.*.md`）同名章节；两处内容如有出入，以各侧声明的权威范围为准——本文件为站外权威。
3. `manual.*.md` 主题模板章节（zh :932-947 / en 对应节）头部插入对应声明（本文件为应用内权威，站外版见仓库 `yate/docs/themes.*.md`）。

声明措辞执行时按双语风格统一；不改写任何正文、不改章节结构（避免与两文件的未来更新冲突）。

## 四、验证方案

- 纯文档变更，按 misc-rules §三豁免 pyright / pytest。
- 手工验证：
  1. 双语成对检查——`docs/README.md` 与两处声明 en/zh 均成对出现（doc-conventions §三）；
  2. `Select-String -Path yate\docs\themes.*.md,yate\resources\manual.*.md -Pattern "权威"`（或对应英文 "authoritative"）确认 4 处声明齐全；
  3. 抽查应用内渲染：跑 `.venv\Scripts\python.exe -m yate` 后 `:help` 打开手册，主题章节正常显示（声明是普通引用块，不破坏 Markdown 渲染）。

## 五、风险与回滚

- 风险：极低；唯一注意点是 manual 文件被 wheel 打包，声明文本随之发布（预期内）。
- 回滚：revert 单提交。
