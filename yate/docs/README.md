# yate/docs -- out-of-tree guides / 站外阅读指南

**English**. This directory holds the out-of-tree reading guides (rendered on
GitHub / Gitee), each topic paired `*.en.md` / `*.zh.md`:

- `extensions.*.md` -- writing yate extensions;
- `lsp.*.md` -- language server setup;
- `themes.*.md` -- theme customization and the shipped templates;
- `yaterc.*.md` -- the `yaterc` configuration reference.

The in-app manual that `:help` renders lives in `yate/resources/manual.*.md`
(shipped inside the wheel for offline reading). Where a topic appears in
both places, this directory is the **out-of-tree authority** and the manual
is the **in-app authority**; each overlapping section carries a provenance
note saying so.

**中文**。本目录存放站外阅读指南（GitHub / Gitee 渲染），各主题均按
`*.en.md` / `*.zh.md` 成对：

- `extensions.*.md` -- 编写 yate 扩展；
- `lsp.*.md` -- 语言服务器配置；
- `themes.*.md` -- 主题定制与随包模板；
- `yaterc.*.md` -- `yaterc` 配置参考。

应用内 `:help` 渲染的手册在 `yate/resources/manual.*.md`（随 wheel 打包、
离线可读）。同一主题两处并存时，本目录为**站外权威**、手册为**应用内权威**，
重叠章节头部均附有来源声明。
