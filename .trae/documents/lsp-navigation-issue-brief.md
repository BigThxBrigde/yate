# Issue IKX5EP 简报（原始素材，不做分析）

来源：https://gitee.com/jermaine/yate/issues/IKX5EP
创建时间：2026-11-22 18:08；状态：open；标签：feature, enhancement；里程碑：P0。

## 标题

ENH - 补齐 LSP 导航与交互能力：DEFINITION / HOVER / OUTLINE / REFERENCES / RENAME / CODE ACTIONS / SIGNATURE HELP

## 目标 / 优先级

| 优先级 | 能力 | 目标 |
|---|---|---|
| P0 | 跳转到定义（`gd`） | 跳转到符号定义；跨文件；LocationLink 目标范围 |
| P1 | Hover 弹窗（`K`） | 新增 `K` 显示 hover，复用现有 hover 卡片；保留 `<f7>` |
| P2 | 文档符号 / 大纲 | 列出当前文档符号树；选择后跳转 |
| P3 | 查找引用（`gr`） | 列出带文件路径和位置的引用；从列表导航，支持跨文件 |
| P4 | 重命名 | 重命名符号，应用 LSP workspaceEdit |
| P5 | 代码操作 | 列出并应用服务器代码操作（包括 quickfix） |
| P6 | 签名帮助 | 在调用点显示参数签名弹窗 |

允许按优先级分批交付。

## 验收标准（逐字保留原意）

环境：pyright-langserver；一个至少包含两个 Python 文件的测试项目（A 定义函数/类，B 导入并调用它）。

- AC1（P0，必须）：在 B 的调用点按 `gd`，跳转到 A 中的定义；返回时 LocationLink 目标范围准确；无 definition provider -> 显式提示，不静默失败，不抛异常。
- AC2（P1，必须）：在符号上按 `K` -> hover 弹窗内容与 `<f7>` 相同；`<f7>` 仍可用；vsc 和 vim 的 keymap 表都以相同方式绑定 `K`，并有架构守卫防止单侧漂移。
- AC3（P3，必须）：按 `gr` -> 显示带文件路径和位置的引用列表；回车/点击可导航，包括 A<->B 跨文件；无引用 -> 显式状态，不崩溃。
- AC4（P2）：文档大纲/文档符号列表，条目可跳转到对应位置；不支持时优雅降级。
- AC5（P4）：重命名应用服务器结果；服务器失败/位置不可编辑 -> 提示，不出现半应用状态。
- AC6（P5/P6）：代码操作和签名帮助可列出/显示；服务器不支持 -> 不报错，不阻塞编辑。
- AC7（全部）：请求为异步，等待绝不阻塞输入；取消 / 关闭文档 / 超时不得留下悬空回调。
- AC8（工程）：pyright 零诊断、完整 pytest 全绿、架构测试全绿；新按键在 vsc/vim 两张表中均有共享常量守卫；`yate/docs/lsp.zh.md` 和 `lsp.en.md` 双语更新；若用户可见按键发生变化则更新应用内手册。

## 边界与兼容性

- 仅涉及 LSP 协议能力；不安装/打包语言服务器；pyright 只是验收用的服务器。
- 保持现有补全 / diagnostics / `<f7>` hover 行为不变；`K`、`gd`、`gr` 是新绑定，不得与现有按键冲突。
- `hoverProvider` 是服务器能力；客户端只声明 `hover.contentFormat`。
- 服务器能力是各特性的开关；能力缺失时以提示信息降级。
- 已知风险：pyright 可能在 URI 中回显编码为 `d%3A` 的盘符，与本地 `path_to_uri` 不匹配（已有的 publishDiagnostics 位置问题）。导航必须使用统一的 URI 到路径映射；不要只修一处。
- 架构：LSP request封装在 `editor_lsp` 叶包中，流程编排在 L3 `flows/*_flows.py`，UI 组件在 `editor_components`；不新增 `Protocol` / `TYPE_CHECKING`；流程模块不持有 App 句柄；新组件的 id / 主题 / 滚动条遵循规则。

## 非目标

- 不以 tree-sitter/regex 本地符号索引作为导航路径（不扩展现有的补全缓冲区回退）。
- 不支持多根工作区符号搜索；大纲仅限当前文档。
- 不提供全局重命名预览面板、不提供代码操作按键绑定自定义、不提供富文本模板系统用于签名弹窗。
- 不重写 LSP 连接管理、增量同步或高亮缓存架构。

## 参考位置

- `yate/editor_lsp/client.py`：initialize 能力声明
- `yate/editor_lsp/manager.py`：请求包装（`request_completion` / `request_hover` 作为模板）
- `yate/flows/lsp_sync.py`：LSP 事件 / diagnostics 接线
- `yate/keymaps/keys.py`、`yate/keymaps/vim.py`、`yate/keymaps/vsc.py`：共享按键常量与绑定表
- `yate/docs/lsp.zh.md`、`yate/docs/lsp.en.md`：双语能力文档
