# YATE AI Agent 集成 Spec

> 需求来源：外部技术规格《技术规格：YATE AI Agent 集成》v1.0.0。
> 本 spec 将其意图完整映射到 yate 仓库的**实际架构**（Textual TUI、L0-L4 分层、
> yaterc 配置），差异处见「适配说明」。

## Why
yate 目前是纯编辑器。按外部规格将其升级为具备 AI Chat + Agent 能力的智能编辑器：
Chat/Agent 运行时切换、多 Provider 多模型动态注册与切换、三级权限的工具引擎、
上下文窗口管理、三种面板布局、审计日志与安全边界。

## 适配说明（外部 spec → yate 实际架构）

| 外部 spec 表述 | yate 实际落地 | 理由 |
|---|---|---|
| ncurses / Rust / <1K 行核心 | Textual TUI / Python 3.12 / 分层架构 | 仓库事实（README、pyproject.toml） |
| `~/.yate/config.toml`（TOML） | yaterc（Python 执行的配置文件），选项结构保持外部 spec 的层级语义 | 仓库既有配置通道（config.py），不新增第二配置体系 |
| `LlmProvider` trait | `AiProvider` 抽象基类 + `build_provider()` 工厂 | 架构规则 R2 禁新增 Protocol；用具体基类 |
| 全局事件总线 `EditorEvent`/`AiEvent` | 回调注入 + Textual messages（`AiFlows` 编排） | 架构规则明令禁止全局 EventBus/字符串事件名 |
| Ollama / OpenRouter / Custom Provider 独立实现 | 均为 `kind="openai"` 兼容端点的**配置预设**（Ollama 无密钥 + 本地 base_url；OpenRouter/自定义 = base_url + key）；仅 OpenAI 与 Anthropic 需要两套协议客户端 | 协议收敛，避免重复实现 |
| `Ctrl+A` 前缀弦（所有键位表） | vsc 键位表用 `Ctrl+A` 前缀弦；vim 键位表 `Ctrl+A` 已被递增占用，等价弦为 `Alt+A` 前缀，均可经 keymap 自定义 | 不破坏 vim 既有键位 |
| `Ctrl+Enter` 发送 | 输入框 `Enter` 发送；`Ctrl+Enter` 仅在 chord 驱动（key_protocol=auto）下可用作发送 | 多数终端无法区分 Ctrl+Enter 与 Enter |
| `models = []` 动态获取 | openai 兼容 Provider 可选 `fetch_models = True`，经 `GET {base_url}/models` 拉取并缓存 | 保留外部 spec 能力 |
| 权限域 Project/Global 持久化 | 本期实现 Once / Session 两级作用域；Project/Global 持久化授权为非目标 | 收敛范围 |

## What Changes
- 新增 L0 叶包 `yate/editor_ai/`：消息/工具/权限类型、SSE 解析、
  `AiProvider` 基类 + OpenAI 兼容 / Anthropic 两套协议客户端、
  `ProviderRegistry`（多 Provider 多模型、激活切换、模型动态拉取）、
  `ToolEngine`（11 个内置工具定义 + 注册表）、Agent 循环、Context Manager、
  权限网关、审计日志写入（全部纯逻辑，不 import textual）。
- 新增 yaterc 选项：`ai` 字典（enabled/default_mode/default_provider/
  default_model/max_tool_rounds/max_tool_calls_per_session/streaming/
  panel_position/panel_size/attach_editor/tool_timeout）与 `ai_providers`
  列表（name/kind/base_url/api_key_env/models/fetch_models），
  解析对齐 `language_servers` / `_extract_screen_saver` 模式；
  环境变量 `YATE_AI_PROVIDER` / `YATE_AI_MODEL` / `YATE_AI_MODE`
  优先于配置（对齐 `YATE_TRACE` 先例）。
- 新增 L2 组件 `yate/editor_view/ai_panel.py`：AI 面板（标题栏含
  模式/模型/连接状态、会话流 Markdown 流式渲染、工具调用卡片、输入区、
  确认 UI、模型选择器），支持 bottom / right / fullscreen 三种布局。
- 新增 L3 流程模块 `yate/ai_flows.py`（`AiFlows`）：会话状态机
  （AiSession：模式/Provider/消息/上下文/权限策略）、面板编排、
  流式渲染节流、取消、编辑器侧工具执行器（缓冲区/光标/选区）注入。
- `Editor` 接线：`AiPanel(id="ai-dock")`、动作与 `:ai` / `:ai-mode` /
  `:ai-model` / `:ai-provider` 命令、键位弦、`app.tcss` 样式（R9）。
- 新增可选依赖组 `ai = ["httpx>=0.27"]`；未安装时面板优雅降级。
- `yate/paths.py` 新增审计日志路径助手；审计日志落 `~/.yate/ai/audit.log`。
- `tests/test_architecture.py` 的 `UI_FREE_PACKAGES` 补入 `editor_ai`。
- 双语文档：`yate/docs/ai-chat.{en,zh}.md` 新增；`yaterc.{en,zh}.md` /
  `yaterc.example` 增补。

## Impact
- Affected specs: 无既有 spec（首个 AI 能力 spec）。
- Affected code:
  - 新文件：`yate/editor_ai/`（types / sse / providers / registry / tools /
    permissions / agent / context / audit）、`yate/editor_view/ai_panel.py`、
    `yate/ai_flows.py`、`tests/test_editor_ai.py`、
    `yate/docs/ai-chat.{en,zh}.md`
  - 修改：`yate/config.py`、`yate/paths.py`、`yate/editor.py`、
    `yate/actions.py`、`yate/commands.py`、`yate/keymaps/vsc.py`、
    `yate/keymaps/vim.py`、`yate/resources/app.tcss`、`pyproject.toml`、
    `tests/test_architecture.py`、`yate/docs/yaterc.{en,zh}.md`、
    `yaterc.example`

## 非目标（Non-goals）
- 对话历史磁盘持久化（本期内存 + 会话内存档；`Ctrl+A n` 新建对话时旧对话
  保留在内存存档列表）。
- 视觉（图片）输入：`ModelInfo.supports_vision` 字段保留，本期不实现。
- 权限作用域 Project / Global 的持久化授权存储。
- ExtensionAPI 暴露 AI 能力（`api.ai` 桥）。
- 编辑器 inline 代码补全。
- MCP / 外部工具协议接入。

## ADDED Requirements

### Requirement: AI 面板与布局
系统 SHALL 提供可开关的 AI 面板（`#ai-dock`），支持三种布局：
**bottom**（默认，占底部 `panel_size` 比例，默认 0.33）、
**right**（编辑器左 60% / AI 右 40%）、**fullscreen**（覆盖编辑区，
`Esc` 返回）。布局经 `Ctrl+A p`（vim：`Alt+A p`）或 `/layout` 循环切换。

#### Scenario: 开关面板
- **WHEN** 用户按下 `Ctrl+A` `a`（vim：`Alt+A` `a`）或执行 `:ai`
- **THEN** AI 面板按当前布局显示，输入区获得焦点；再次执行隐藏并回落焦点到编辑区

#### Scenario: 布局切换
- **WHEN** 用户执行 `Ctrl+A` `p`
- **THEN** 面板在 bottom → right → fullscreen → bottom 间循环，会话内容不丢失

#### Scenario: 优雅降级
- **WHEN** 运行环境未安装 httpx（未装 `yate[ai]`）
- **THEN** 面板仍可打开，发送时在面板内提示安装命令，不崩溃、不产生后台任务

### Requirement: 快捷键与斜杠命令
系统 SHALL 提供前缀弦快捷键（vsc：`Ctrl+A` 前缀；vim：`Alt+A` 前缀）与
面板内斜杠命令两套入口：

| 键（vsc / vim） | 功能 |
|---|---|
| `Ctrl+A a` / `Alt+A a` | 打开/关闭 AI 面板 |
| `Ctrl+A c` / `Alt+A c` | 切换到 Chat 模式 |
| `Ctrl+A g` / `Alt+A g` | 切换到 Agent 模式 |
| `Ctrl+A m` / `Alt+A m` | 打开模型选择器 |
| `Ctrl+A p` / `Alt+A p` | 切换面板布局 |
| `Ctrl+A n` / `Alt+A n` | 新建对话（旧对话保留在内存存档） |
| `Ctrl+A d` / `Alt+A d` | 显示最近工具调用详情（参数/结果/用量） |
| `Esc` | 取消当前 AI 生成 |
| `Enter` | 发送消息（chord 驱动下 `Ctrl+Enter` 同义） |

面板输入框支持斜杠命令：`/mode chat|agent`、`/model [provider/]model`、
`/models`（选择器）、`/provider <name>`、`/add <file>`、`/layout`、
`/new`。全局 `:` 命令提供等价子集：`:ai`、`:ai-mode`、`:ai-model`、
`:ai-provider`。

#### Scenario: 斜杠命令
- **WHEN** 用户在面板输入 `/model openai/gpt-4o`
- **THEN** 跨 Provider 切换到 openai 的 gpt-4o，头部状态刷新，历史保留

### Requirement: Provider 抽象与注册表（多模型接入）
系统 SHALL 以 `AiProvider` 抽象基类（`id()` / `chat()` 流式 /
`supports_tools()` / `supports_streaming()` / `models()`）+ 工厂函数实现
Provider 抽象；`ProviderRegistry` 持有全部 Provider 与
`active_provider` / `active_model`，支持注册、跨 Provider/模型切换、
列出模型（`ModelInfo`：id / display_name / context_window /
supports_tools / provider_id）。内置两套协议客户端：
**OpenAI 兼容**（覆盖 OpenAI / Ollama / OpenRouter / 自定义端点）与
**Anthropic Messages**（均为 SSE 流式）。

#### Scenario: 切换 Provider 与模型
- **WHEN** yaterc 声明 openai、anthropic、ollama（kind=openai、无密钥、
  localhost:11434）三个 Provider，用户执行 `/provider anthropic` 后
  `/model claude-haiku-4-20250514`
- **THEN** 后续对话走新 Provider/模型的端点与密钥，对话历史保留

#### Scenario: 工具能力自动回退
- **WHEN** 处于 Agent 模式时切换到 `supports_tools=False` 的模型
- **THEN** 自动回退到 Chat 模式并在面板提示，不发起带工具的请求

#### Scenario: 模型动态获取
- **WHEN** 某 Provider 配置 `fetch_models = True` 且未写 models 列表
- **THEN** `/models` 选择器按需经 `GET {base_url}/models` 拉取（openai
  兼容端点），结果缓存；拉取失败时回退为手动输入模型名

### Requirement: Chat / Agent 双模式
系统 SHALL 维护 `AiSession`（mode / provider / messages / tool_engine /
context / 权限策略），支持运行时切换且**保留完整对话历史**，仅改变工具
可用性。能力矩阵：

| 能力 | Chat 模式 | Agent 模式 |
|------|-----------|------------|
| 对话/问答 | ✅ | ✅ |
| 读取编辑器缓冲区（上下文注入） | ✅ | ✅ |
| 读取文件系统（工具） | ❌ | ✅ |
| 写入/修改文件（工具） | ❌ | ✅（需权限） |
| 执行 Shell 命令（工具） | ❌ | ✅（需权限） |
| 工具调用 | ❌ | ✅ |

Chat 模式 SHALL 流式渲染回复；`Esc` 取消并保留已收到的部分（标注"已中断"）。

### Requirement: Agent 工具引擎
Agent 模式 SHALL 提供工具引擎：`ToolDefinition`（name / description /
parameters JSON Schema / permission）、`ToolCall`、`ToolResult`
（output / is_error）。内置工具与默认权限：

| 工具名 | 权限 | 描述 |
|--------|------|------|
| `read_file` | Safe | 读取指定文件内容 |
| `list_directory` | Safe | 列出目录内容 |
| `search_in_files` | Safe | 项目内文本搜索 |
| `get_editor_content` | Safe | 当前编辑器缓冲区内容 |
| `get_cursor_position` | Safe | 光标位置与选中范围 |
| `write_file` | Confirm | 写入/创建文件 |
| `edit_file` | Confirm | 编辑文件（替换指定内容） |
| `insert_at_cursor` | Confirm | 光标处插入文本 |
| `replace_selection` | Confirm | 替换当前选中内容 |
| `run_command` | Dangerous | 执行 Shell 命令 |
| `run_tests` | Dangerous | 执行项目测试命令 |

**Agent 循环**：用户输入 → LLM → 无 tool_calls 则流式输出结束；
有 tool_calls 则逐个经权限网关（Safe 自动执行；Confirm 弹确认 UI，
可选 允许一次/允许本次会话/拒绝；Dangerous 弹警告 + 确认），结果回传
LLM 继续，直到无 tool_calls 或达上限。每次工具调用以可折叠卡片
（`⚙ read_file("src/main.rs") ✓`）在会话流可见。
`max_tool_rounds`（默认 25，循环轮次）与
`max_tool_calls_per_session`（默认 50，单对话累计）双上限。

#### Scenario: Confirm 工具确认
- **WHEN** Agent 发起 `write_file`
- **THEN** 确认 UI 显示工具名/路径/内容预览（20 行）与
  `[a]允许一次 [s]允许本次会话 [d]拒绝 [v]查看完整内容`；
  拒绝时"用户拒绝该操作"作为工具结果回填 LLM

#### Scenario: 会话级授权
- **WHEN** 用户对某工具选择"允许本次会话"
- **THEN** 本对话内该工具后续调用不再询问；新建对话后授权失效

#### Scenario: 双上限终止
- **WHEN** 循环轮次达 `max_tool_rounds` 或累计调用达
  `max_tool_calls_per_session`
- **THEN** 循环终止并提示，不再发起新的模型请求

#### Scenario: 编辑器侧工具
- **WHEN** Agent 调用 `get_editor_content` / `insert_at_cursor` /
  `replace_selection` / `get_cursor_position`
- **THEN** 执行器操作当前编辑器缓冲区（注入的具体对象/回调），
  插入与替换进 undo 历史，可 Ctrl+Z 撤销

### Requirement: 权限网关与安全边界
系统 SHALL 实现权限网关：`ToolPermission`（Safe/Confirm/Dangerous）+
可配置覆盖（yaterc `[ai.permissions]` 语义：工具名 → 级别；glob
allow_patterns / deny_patterns 优先级 deny > allow > 默认级别）。安全边界：
- **文件系统沙箱**：Agent 文件工具只能访问 workspace 根内路径，
  `..` 与根外绝对路径被拒绝并以错误结果回填
- **敏感文件**：`.env`、`*.key`、`*.pem` 等默认 deny（写入与读取均拒）
- **命令白名单**：`run_command` 命中 allow_patterns（如 `git status`、
  `ls *`）自动放行，命中 deny_patterns（如 `rm -rf *`）强制拒绝
- **超时**：Shell 命令默认 30 秒超时（`tool_timeout` 可配）
- 所有网关决策在审计日志留痕

#### Scenario: deny 优先
- **WHEN** 某命令同时命中 allow 与 deny 模式
- **THEN** 按拒绝处理并提示原因

#### Scenario: 沙箱逃逸拒绝
- **WHEN** Agent 请求读取 `../../etc/passwd`
- **THEN** 网关拒绝，工具结果为路径越界错误，不发生文件读取

### Requirement: 审计日志
系统 SHALL 将全部工具调用（时间戳、工具名、参数摘要、结果摘要、
用户决策）追加写入 `~/.yate/ai/audit.log`（路径经 `yate.paths` 解析）；
写入为尽力而为，失败只记 tracing 警告，不影响编辑器与 Agent 循环；
日志内容不包含 API 密钥。

#### Scenario: 审计留痕
- **WHEN** Agent 的 `write_file` 被用户拒绝
- **THEN** audit.log 追加一条 `[write_file] <path> → DENIED` 记录

### Requirement: Context Manager
系统 SHALL 提供上下文管理：System prompt（编辑器能力 + 工具列表 + 当前
模式说明）+ EditorContext 自动注入（文件路径、语言、光标行、选区、
可见范围 + 当前文件内容按 `attach_editor` 截断注入）+ FileContext
（`/add <file>` 手动添加，可多个）。token 预算按模型 `context_window`
估算（chars/4 启发式），超窗时按优先级截断：对话历史 → 文件上下文 →
编辑器上下文。

#### Scenario: 编辑器上下文注入
- **WHEN** 用户在打开 `main.rs`、光标第 12 行时提问"这个函数有什么问题"
- **THEN** 请求自动携带 EditorContext（路径/语言/光标/可见范围与截断内容），
  模型可针对当前文件回答

#### Scenario: 超窗截断
- **WHEN** 对话累计接近模型 context_window
- **THEN** 最旧的对话轮次先被截断，System prompt 与最近上下文保留

### Requirement: 配置与环境变量覆盖
yaterc SHALL 支持以下选项（层级语义对齐外部 spec，形式为 Python 变量）：

```python
ai = {
    "enabled": True,
    "default_mode": "chat",           # "chat" | "agent"
    "default_provider": "openai",
    "default_model": "gpt-4o",
    "max_tool_rounds": 25,
    "max_tool_calls_per_session": 50,
    "streaming": True,
    "panel_position": "bottom",       # "bottom" | "right" | "fullscreen"
    "panel_size": 0.33,
    "attach_editor": True,            # 编辑器上下文自动注入
    "tool_timeout": 30,               # 秒
    "permissions": {                  # 工具名 → "safe"|"confirm"|"dangerous"
        "run_tests": "confirm",
    },
    "allow_patterns": {"run_command": ["git status", "git diff", "ls *"]},
    "deny_patterns": {"write_file": ["**/.env", "**/*.key", "**/*.pem"],
                      "run_command": ["rm -rf *", "dd *"]},
}
ai_providers = [
    {"name": "openai", "kind": "openai",
     "api_key_env": "OPENAI_API_KEY",
     "base_url": "https://api.openai.com/v1",
     "models": ["gpt-4o", "gpt-4o-mini", "o3-mini"]},
    {"name": "anthropic", "kind": "anthropic",
     "api_key_env": "ANTHROPIC_API_KEY",
     "models": ["claude-sonnet-4-20250514", "claude-haiku-4-20250514"]},
    {"name": "ollama", "kind": "openai",
     "base_url": "http://localhost:11434/v1",
     "models": ["qwen2.5-coder", "deepseek-coder-v2"]},
    {"name": "openrouter", "kind": "openai",
     "api_key_env": "OPENROUTER_API_KEY",
     "base_url": "https://openrouter.ai/api/v1",
     "fetch_models": True},
]
```

解析遵循现有模式（独立 `_extract_ai` / `_extract_ai_providers`，错误进
`config.errors`，绝不使启动崩溃）。环境变量 `YATE_AI_PROVIDER` /
`YATE_AI_MODEL` / `YATE_AI_MODE` 优先于配置文件（对齐 `YATE_TRACE`
先例）。

#### Scenario: 非法配置
- **WHEN** `ai_providers` 某条目缺 `name`/`kind` 或 `ai.panel_size` 越界
- **THEN** 该条目/选项被跳过并报告错误，其余配置与编辑器启动不受影响

#### Scenario: 环境变量优先
- **WHEN** 配置 default_provider=openai 且设置了 `YATE_AI_PROVIDER=anthropic`
- **THEN** 启动后激活 Provider 为 anthropic

### Requirement: 流式渲染与崩溃隔离
系统 SHALL 流式渲染（节流 ≤30fps，Markdown 基础渲染：粗体/代码块高亮/
列表/链接，流式光标）。AI 层懒加载：首次打开面板才 import `editor_ai`
与 httpx，启动时间增量 <50ms；任何 Provider/Agent 异常被捕获并在面板
内呈现为错误行，编辑器核心不受影响。

#### Scenario: 网络错误隔离
- **WHEN** 请求因网络错误失败
- **THEN** 面板显示错误信息，输入区恢复可用，编辑器其它功能不受影响

### Requirement: 架构与安全合规
- `editor_ai/` 为 L0 叶包：不 import textual / editor_view / yate.editor /
  yate.app；加入 `UI_FREE_PACKAGES` 守卫面；日志走 tracing 惰性 `%`
  （R12），严禁记录 API 密钥与完整请求体
- Provider 抽象用抽象基类 + 工厂（R2 禁 Protocol）；全仓无 `TYPE_CHECKING`
  （R6）
- `AiFlows` 遵守 R11（不向上 import `yate.editor`、不持 App 句柄，worker/
  屏幕/会话查询经注入回调）；编辑器侧工具执行器由 L3 注入具体对象
  （R8）；`AiPanel` 为 L2 自持组件（自持主题 + `apply_slim_scrollbars`，
  R13），消费的键 `event.stop()` 防二次派发（R10）
- **不引入全局 EventBus / 字符串事件名**（外部 spec 的事件总线按回调 +
  Textual messages 落地）

#### Scenario: 架构门禁
- **WHEN** 运行 `python -m pyright yate/ tests/ tools/` 与
  `python -m pytest tests/ -q`
- **THEN** pyright 零诊断、pytest 全绿（含 `tests/test_architecture.py`
  全部用例与新增 `editor_ai` 守卫面）

### Requirement: 非功能性需求
| 指标 | 目标值 |
|------|--------|
| 首 token 延迟 | < 800ms（网络正常时） |
| 流式渲染帧率 | ≥ 20fps（节流 ≤30fps） |
| 内存占用增量 | < 30MB（不含响应缓存） |
| 启动时间增量 | < 50ms（AI 模块懒加载） |
| 工具执行超时 | 默认 30s，`tool_timeout` 可配置 |
| 上下文窗口 | 动态适配各模型（按 `context_window` 配置） |
| 崩溃隔离 | AI 层异常不影响编辑器核心 |

#### Scenario: 懒加载启动
- **WHEN** yaterc 含合法 ai 配置但用户从未打开 AI 面板
- **THEN** 启动路径不 import httpx / editor_ai，启动耗时增量可忽略

### Requirement: 文档双语同步
系统 SHALL 同步双语文档：`yate/docs/ai-chat.en.md` 与 `ai-chat.zh.md`
成对新增（面板用法、模式矩阵、快捷键表、Provider 配置预设、密钥经环境
变量注入的安全说明、`pip install yate[ai]`）；`yaterc.en.md` /
`yaterc.zh.md` 与 `yaterc.example` 成对增补 `ai` / `ai_providers`。

## MODIFIED Requirements

### Requirement: 底部 dock 与布局（editor.py compose）
`#bottom-dock` SHALL 在终端面板之后新增 `AiPanel(id="ai-dock")`（bottom
布局的宿主）；right 布局将面板挂入 `#body` 右侧分割、fullscreen 以覆盖
层实现——三种布局均由 `Editor` 构造并传 id（R9），样式落入
`yate/resources/app.tcss`。

### Requirement: yaterc 选项解析（config.py）
`config.py` SHALL 新增 `AiProviderSpec` / `AiConfig` /
`AiPermissionsConfig` 数据类与 `_extract_ai` / `_extract_ai_providers`
解析函数（对齐 `LanguageServerSpec` / `_extract_screen_saver` 模式：
独立于 `_KNOWN_OPTIONS` 标量通道、错误进 `config.errors`、环境变量
覆盖钩子）。

## REMOVED Requirements
（无）
