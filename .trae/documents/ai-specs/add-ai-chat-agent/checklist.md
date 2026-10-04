# Checklist

## 面板与交互
- [ ] `Ctrl+A a`（vim `Alt+A a`）与 `:ai` 可开关 `#ai-dock` 面板，焦点切换正确
- [ ] `Ctrl+A p` 循环切换 bottom / right / fullscreen 布局，会话内容不丢失
- [ ] `Ctrl+A n` 新建对话，旧对话保留在内存存档
- [ ] `Ctrl+A d` 显示最近工具调用详情（参数/结果/用量）
- [ ] 未安装 httpx 时打开面板不崩溃，发送时面板内给出 `yate[ai]` 安装提示

## 模式
- [ ] `Ctrl+A c` / `Ctrl+A g`、`/mode chat|agent`、`:ai-mode` 均可切换模式，
      切换保留完整对话历史
- [ ] Chat 模式不下发任何工具定义（能力矩阵成立）
- [ ] Agent 模式工具调用以折叠卡片可见（`⚙ read_file("src/main.rs") ✓`）
- [ ] Agent 模式下切到 `supports_tools=False` 模型自动回退 Chat 并提示

## Provider 与模型
- [ ] yaterc 可配置 openai / anthropic / ollama（kind=openai 无密钥）/ openrouter
      预设，`:ai-model` / `/model [provider/]model`、`/provider` 切换生效，
      `:ai-model` / `/models` 列出全部并标记当前项
- [ ] `fetch_models = True` 时 `/models` 经 `GET {base_url}/models` 动态拉取，
      失败回退手动输入模型名
- [ ] 切换 Provider/模型后对话历史保留

## Chat 模式
- [ ] 流式渲染（节流 ≤30fps、Markdown 基础渲染、流式光标）
- [ ] `Esc` 取消并保留已收到的部分，标注"已中断"
- [ ] EditorContext 自动注入（路径/语言/光标/选区/可见范围 + `attach_editor`
      截断内容）；`/add <file>` 手动附加文件上下文

## Agent 与权限
- [ ] 11 个内置工具全部可用且权限级别符合外部 spec 默认表
- [ ] Safe 工具自动执行；Confirm 弹确认 UI（允许一次/允许本次会话/拒绝/
      查看完整内容 + 20 行预览）；Dangerous 弹警告 + 确认
- [ ] 会话级授权在新建对话后失效
- [ ] `write_file` / `run_command` 被拒绝时"用户拒绝"作为工具结果回填模型
- [ ] `max_tool_rounds`（25）与 `max_tool_calls_per_session`（50）双上限生效，
      超限终止且不再发起新请求
- [ ] 工具参数经 JSON Schema 校验：编造参数/缺必填不执行，以 `is_error`
      回填模型自我修正（防参数幻觉）
- [ ] 同一（工具, 参数）连续 ≥3 次调用时注入防循环警告结果
- [ ] 编辑器侧工具（get_editor_content / get_cursor_position /
      insert_at_cursor / replace_selection）操作真实缓冲区，写操作可 Ctrl+Z 撤销

## 安全边界
- [ ] 文件工具沙箱：workspace 根内路径才可访问，`..` / 根外绝对路径拒绝
- [ ] `.env` / `*.key` / `*.pem` 默认 deny（deny > allow > 默认级别）
- [ ] `run_command` 命中 allow_patterns 自动放行、命中 deny_patterns 强制拒绝，
      同时命中时拒绝
- [ ] Shell 命令 30s 超时（`tool_timeout` 可配）
- [ ] 审计日志写入 `~/.yate/ai/audit.log`（时间戳/工具/参数/结果摘要/决策），
      写失败仅 tracing 警告，任何日志不含 API 密钥

## 上下文与配置
- [ ] token 预算按模型 context_window 估算，超窗按 对话历史 → 文件上下文 →
      编辑器上下文 优先级截断，System prompt 保留
- [ ] yaterc `ai` / `ai_providers` 全选项解析；非法条目跳过并报告，启动不崩
- [ ] `YATE_AI_PROVIDER` / `YATE_AI_MODEL` / `YATE_AI_MODE` 优先于配置

## 架构与非功能
- [ ] Agent 循环为自研轻量实现；未引入 langchain / langgraph / llamaindex，
      pyproject 新增依赖仅 `ai = ["httpx>=0.27"]`
- [ ] `editor_ai/` 不 import textual / editor_view / yate.editor / yate.app；
      `UI_FREE_PACKAGES` 守卫含 `editor_ai`，架构测试全绿
- [ ] 无全局 EventBus / 字符串事件名；无新增 Protocol / TYPE_CHECKING；
      AiFlows 不持 App 句柄、不向上 import yate.editor
- [ ] AiPanel 自持主题与滚动条（R13）、按键无二次派发（R10）、id 由 Editor
      传入且 `app.tcss` 已同步（R9）
- [ ] 懒加载：未打开面板时启动路径不 import httpx / editor_ai（启动增量 <50ms）
- [ ] AI 层异常在面板内呈现为错误行，编辑器核心不受影响
- [ ] 日志走 tracing 惰性 `%`（R12）
- [ ] `python -m pyright yate/ tests/ tools/` 零诊断
- [ ] `python -m pytest tests/ -q` 全绿

## 文档
- [ ] `yate/docs/ai-chat.en.md` 与 `ai-chat.zh.md` 成对新增且内容对应
- [ ] `yaterc.en.md` / `yaterc.zh.md` / `yaterc.example` 成对增补 `ai` /
      `ai_providers` 全部选项说明
