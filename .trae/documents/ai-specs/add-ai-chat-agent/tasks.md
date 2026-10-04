# Tasks

> 按外部 spec 的五阶段路线图组织，每阶段末尾有可执行验收门禁。
> 全部阶段共同约束：架构规则（R2/R6/R9-R13）、pyright strict 零诊断、
> `python -m pytest tests/ -q` 全绿。

## Phase 1：基础设施（Provider 抽象 + 配置）

- [ ] Task 1: L0 叶包 `yate/editor_ai/` 类型与 SSE 基础
  - [ ] 1.1 `types.py`：`ChatMessage`（role/content/tool_calls/tool_call_id）、
        `ToolDefinition`（name/description/parameters/permission）、`ToolCall`、
        `ToolResult`（output/is_error）、`ModelInfo`（id/display_name/
        context_window/supports_tools/supports_vision/provider_id）、
        `TokenUsage`、`StreamChunk`（Text | ToolCall | Done{finish_reason,
        usage} | Error）dataclass
  - [ ] 1.2 `sse.py`：SSE 行解析（`data:` / `event:` / `[DONE]`），纯函数单测
  - [ ] 1.3 `providers.py`：`AiProvider` 抽象基类（`id()` / `chat()` async
        生成器流式 / `supports_tools()` / `supports_streaming()` /
        `models()`）+ `OpenAICompatProvider`（含 `fetch_models` 动态拉取
        `GET {base_url}/models`）+ `AnthropicProvider` +
        `build_provider(spec)` 工厂；httpx 懒导入（对齐 `tools/pack/icon.py`
        先例），未安装抛可识别异常；密钥仅经 `api_key_env` 读环境变量
  - [ ] 1.4 `registry.py`：`ProviderRegistry`——register / switch(provider,
        model) / list_models() / active_provider / active_model；切换时
        `supports_tools=False` 的模型在 Agent 模式触发回退信号
  - [ ] 1.5 `tests/test_editor_ai.py`：两种 kind 的请求体构造、SSE 解析、
        增量聚合、工具调用 JSON 解析、registry 切换与能力回退
        （`httpx.MockTransport` 伪造流式响应与 /models 响应）
- [ ] Task 2: yaterc 选项 `ai` / `ai_providers`（yate/config.py）
  - [ ] 2.1 `AiProviderSpec`（name/kind/base_url/api_key_env/models/
        fetch_models）+ `AiConfig`（enabled/default_mode/default_provider/
        default_model/max_tool_rounds/max_tool_calls_per_session/streaming/
        panel_position/panel_size/attach_editor/tool_timeout/permissions/
        allow_patterns/deny_patterns）+ `AiPermissionsConfig` 数据类；
        `_extract_ai` / `_extract_ai_providers`（对齐 `language_servers` /
        `_extract_screen_saver` 模式，错误进 `config.errors`）
  - [ ] 2.2 环境变量覆盖 `YATE_AI_PROVIDER` / `YATE_AI_MODEL` /
        `YATE_AI_MODE`（优先于配置，对齐 `YATE_TRACE` 先例）
  - [ ] 2.3 `tests/test_config.py` 增补：合法多 Provider / 非法条目跳过 /
        pattern 校验 / 环境变量优先 / 全部缺省
  - [ ] 2.4 `yaterc.example` 增补（openai / anthropic / ollama 预设 /
        openrouter fetch_models / permissions 段）

## Phase 2：Chat 模式（面板 + 流式 + 上下文）

- [ ] Task 3: L2 面板组件 `yate/editor_view/ai_panel.py`（bottom 布局）
  - [ ] 3.1 `AiPanel(Vertical)`：标题栏（模式 chip + 当前 provider/model +
        连接状态）+ 会话流（Markdown 渲染：粗体/代码块/列表/链接，节流
        ≤30fps，流式光标）+ 输入区（Enter 发送）；`.toggle()` 语义对齐
        `TerminalPanel`；自持主题（`theme.subscribe`）+
        `apply_slim_scrollbars`（R13）；消费的键 `event.stop()`（R10）
  - [ ] 3.2 斜杠命令解析与执行入口：`/mode` `/model` `/models` `/provider`
        `/add` `/layout` `/new`；`Esc` 取消生成
  - [ ] 3.3 确认 UI（Phase 4 接工具用）：`[a]允许一次 [s]允许本次会话
        [d]拒绝 [v]查看完整内容`，含 20 行预览
  - [ ] 3.4 模型选择器（`/models` / `Ctrl+A m`）：面板内列表选择
- [ ] Task 4: L3 会话与编排 `yate/ai_flows.py`（`AiFlows`）
  - [ ] 4.1 `AiSession` 状态机：mode / provider registry / messages /
        context / 权限策略（会话级授权集合）；模式切换保留历史；
        `/new` 归档旧对话（内存存档列表）
  - [ ] 4.2 Chat 流程：发送 → 流式写面板（worker 经注入 `spawn` 绑定方法，
        对齐能力注入模式）→ 节流渲染 → Esc 取消（保留已收到的部分，标注
        "已中断"）→ 异常捕获呈现为面板错误行（崩溃隔离）
  - [ ] 4.3 Context Manager 雏形（`yate/editor_ai/context.py`）：
        System prompt（能力 + 工具 + 模式说明）+ EditorContext 注入
        （路径/语言/光标/选区/可见范围 + `attach_editor` 截断内容）+
        `/add` FileContext
  - [ ] 4.4 编辑器上下文来源经 L3 注入回调（session 具体对象），AiFlows
        不向上 import `yate.editor`、不持 App 句柄
- [ ] Task 5: 接线（editor.py / actions / commands / keymaps / app.tcss）
  - [ ] 5.1 `yate/editor.py`：构造 `AiPanel(id="ai-dock")` 挂入
        `#bottom-dock`（compose 于 editor.py:404-420 扩展）；懒加载
        （首次打开才构建 AiFlows 依赖）；`on_unmount` 清理
  - [ ] 5.2 `yate/actions.py` / `yate/commands.py`：动作 `ai_panel`；
        命令 `:ai` / `:ai-mode` / `:ai-model` / `:ai-provider`
  - [ ] 5.3 `yate/keymaps/vsc.py`（`Ctrl+A` 前缀弦：a/c/g/m/p/n/d）与
        `yate/keymaps/vim.py`（`Alt+A` 前缀弦，Ctrl+A 递增保留）
  - [ ] 5.4 `yate/resources/app.tcss` 增补 `#ai-dock` 样式（R9）

## Phase 3：多 Provider 打磨

- [ ] Task 6: 跨 Provider 体验补全
  - [ ] 6.1 `/model [provider/]model` 跨 Provider 切换、`/provider` 切换
        （历史保留）；能力回退提示接入面板（Task 1.4 的回退信号）
  - [ ] 6.2 `fetch_models` 拉取缓存与失败回退手动输入（接 `/models` 选择器）
  - [ ] 6.3 `tests/test_editor_ai.py` 增补：跨 Provider 切换、动态拉取
        成功/失败路径

## Phase 4：Agent 模式（工具引擎 + 权限）

- [ ] Task 7: 工具引擎与内置工具（L0）
  - [ ] 7.1 `yate/editor_ai/tools.py`：工具注册表（ToolDefinition →
        executor Callable）+ `run_tool()` 统一执行入口（结果包装为
        ToolResult，异常转 is_error）
  - [ ] 7.2 文件系统工具（沙箱内）：`read_file` / `list_directory` /
        `search_in_files` / `write_file` / `edit_file`——路径解析锚定
        workspace 根，`..` 与根外绝对路径拒绝
  - [ ] 7.3 Shell 工具：`run_command` / `run_tests`——subprocess 带
        `tool_timeout` 超时
  - [ ] 7.4 `tests/test_editor_ai.py`：沙箱逃逸拒绝、超时、edit_file
        替换语义
- [ ] Task 8: 权限网关与审计（L0）
  - [ ] 8.1 `yate/editor_ai/permissions.py`：`ToolPermission` 三级 +
        `PermissionPolicy`（级别覆盖 + glob allow/deny patterns，
        deny > allow > 默认级别；会话级授权集合 Once/Session）
  - [ ] 8.2 `yate/editor_ai/audit.py`：审计日志追加写（时间戳/工具/参数
        摘要/结果摘要/决策），路径经 `yate.paths` 助手落
        `~/.yate/ai/audit.log`；写失败仅 tracing 警告；不含密钥
  - [ ] 8.3 `tests/test_editor_ai.py` + `tests/test_paths.py`：deny 优先、
        敏感文件默认 deny、授权作用域、审计记录内容与失败静默
- [ ] Task 9: Agent 循环（L0）
  - [ ] 9.1 `yate/editor_ai/agent.py`：`run_agent_turn()`——模型响应 →
        tool_calls → 权限网关（confirm_callback 注入，返回
        allow_once/allow_session/deny）→ 执行 → 结果回填 → 续环；
        `max_tool_rounds` / `max_tool_calls_per_session` 双上限；
        每轮事件经回调流式上报（供面板卡片渲染）
  - [ ] 9.2 编辑器侧工具执行器（L3 注入）：`get_editor_content` /
        `get_cursor_position` / `insert_at_cursor` / `replace_selection`
        操作 session 缓冲区，写操作进 undo 历史
  - [ ] 9.3 `AiFlows` Agent 流程接线：工具调用卡片渲染（
        `⚙ read_file("src/main.rs") ✓` 折叠展开）、确认 UI 接
        confirm_callback、`Ctrl+A d` 工具详情
  - [ ] 9.4 `tests/test_editor_ai.py`：假 provider 驱动多轮工具调用、
        确认三路径（once/session/deny 回填）、双上限终止、模式矩阵
        （Chat 不下发工具）

## Phase 5：打磨与稳定

- [ ] Task 10: 上下文预算与布局
  - [ ] 10.1 token 预算（chars/4 估算 × 模型 context_window），超窗按
        对话历史 → 文件上下文 → 编辑器上下文优先级截断
  - [ ] 10.2 布局切换 bottom / right（`#body` 右侧分割）/ fullscreen
        （覆盖层，Esc 返回），`Ctrl+A p` 循环 + `/layout`
  - [ ] 10.3 Pilot 冒烟（textual-pilot）：面板开关、布局循环、发送与
        流式渲染、确认 UI 交互（假 provider 本地回放，不出网）
- [ ] Task 11: 守卫与全量门禁
  - [ ] 11.1 `tests/test_architecture.py` `UI_FREE_PACKAGES`（约 :88）
        补入 `editor_ai`
  - [ ] 11.2 `python -m pyright yate/ tests/ tools/` 零诊断
  - [ ] 11.3 `python -m pytest tests/ -q` 全绿（含架构 22+ 用例）
  - [ ] 11.4 懒加载验证：未打开面板时启动路径不 import httpx /
        editor_ai（探针断言 sys.modules）
- [ ] Task 12: 双语文档（成对新增/更新，硬约束）
  - [ ] 12.1 `yate/docs/ai-chat.en.md` + `ai-chat.zh.md`：面板与布局、
        模式矩阵、快捷键表、斜杠命令、Provider 配置预设（openai/
        anthropic/ollama/openrouter）、权限模型与安全边界、密钥经环境
        变量注入、`pip install yate[ai]`、审计日志位置
  - [ ] 12.2 `yate/docs/yaterc.en.md` + `yaterc.zh.md` 增补 `ai` /
        `ai_providers` 全部选项

# Task Dependencies
- Task 2 与 Task 1 相互独立，可并行
- Task 3、Task 4 依赖 Task 1-2；Task 4.3 依赖 Task 1.1（类型）
- Task 5 依赖 Task 3、Task 4
- Task 6 依赖 Task 1.4、Task 3、Task 4（选择器与流程就绪）
- Task 7 依赖 Task 1（类型）；Task 8 依赖 Task 7（工具定义）；
  Task 9 依赖 Task 7、Task 8、Task 4
- Task 10 依赖 Task 5、Task 9
- Task 11 依赖 Task 1-10 全部
- Task 12.1 可与 Task 3-6 并行；Task 12.2 依赖 Task 2 定稿
- 每个 Phase 收尾跑一次该阶段全部新增测试 + 架构测试
