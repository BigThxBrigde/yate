# 子计划 plan-i：配置域重构——单一选项表 + config 拆分（A8 / A9 / A20 复核）

> 所属波次：**wave-4**（与 extension-rollback-plan-d 文件不重叠，可并行；主代理执行；依赖 wave-3 plan-g 完成——`prompt_completion.py` 届时位于 `yate/flows/`）。
> 执行者：**主代理**。
> 来源：评审 A8 / A9 / A20。

## 一、输入

- A8：`:set` 选项知识双份硬编码——`commands.py:190-253` `_set` if/elif 链（keymap/theme/shell/terminal_height/show_hidden/readonly/filetype 各带校验文案，`terminal_height` 的 3..40 校验内联）；`flows/prompt_completion.py:21-24`（迁移后路径）`_SET_OPTIONS` 元组另维护一份选项名；`prompt_completion.py:13` 还 import `yate.editor_syntax.available_filetypes`。
- A9：`config.py` 924 行多职责（模块 docstring yaterc 说明 :1-50、常量表 :61-81、数据类 :84 起、load/exec/合并/校验在后半）。
- A20：`editor.py:805-840` 的 `set_readonly` / `set_filetype` 属 `:set` 后端 setter（`set_theme` :778-803 亦然），A8 表驱动落地后复核 editor.py 行数。

## 二、独占文件清单

1. `yate/config.py`（保留数据类与常量；瘦身为"选项 schema + 配置数据类"）
2. `yate/yaterc.py`（新增：rc 文件发现 / exec 加载 / 合并 / 校验 / `load_config` / `default_rc_paths` / `user_config_path` / `find_project_config` / `RC_FILENAME`；保持 L0，仅 import `yate.config` 数据类与 `yate.logs`）
3. `yate/commands.py`（`_set` 表驱动重构）
4. `yate/flows/prompt_completion.py`（`_SET_OPTIONS` 改由 config 选项表派生）
5. `yate/editor.py`（无逻辑改动；仅当 setter 迁移收益明确时把 `:set` 相关 setter 收拢，见 §3.4）
6. 消费方 import 更新：`yate/cli.py:299`（`load_config` / `default_rc_paths`）、`yate/diagnostics.py:251`（函数内 `from yate.config import find_project_config, user_config_path`）、`tools/smoke_test/harness.py:35` 与 `tools/smoke_test/scenarios/palette_preview.py:24`（`load_config`）
7. `tests/test_architecture.py`（`UI_FREE_PACKAGES` 追加 `"yaterc.py"`——R4 守卫面，config.py:88 既有条目旁）
8. 测试：`tests/test_config.py`（加载/校验用例的 import 路径核对）、`tests/test_action_table.py`（`_set` 行为回归）、新增 `tests/test_set_options.py`

## 三、具体修改

### 3.1 A9——config.py 拆分（先做，3.2 依赖新结构）

- `config.py` 留：模块 docstring（改写为"配置数据模型"）、`_KNOWN_OPTIONS` / `_VALID_KEYMAPS` / `_VALID_KEY_PROTOCOLS` / `_VALID_TRACE_LEVELS` 常量、全部 dataclass（`YateConfig` / `LanguageServerSpec` / `ScreenSaverConfig` / `FilePreviewConfig`）；
- `yaterc.py` 拿走：`RC_FILENAME`、rc 发现路径函数、exec/合并/校验逻辑、`load_config`（含 N30 回调注入签名 `load_config(register_theme=..., load_theme_paths=...)` 原样搬运）、`default_rc_paths` / `user_config_path` / `find_project_config`；
- 消费方更新（§二.6 清单，35 处 grep 实测中仅 6 处 import 移动符号，其余只用数据类不动）；
- 拆分后两文件各自 < 600 行（预估 config ~350 / yaterc ~400）。

### 3.2 A8——单一选项表

在 `config.py` 新增（配置专属类型，非公共类型层）：

```python
@dataclass(frozen=True)
class SetOption:
    """One ``:set`` option: aliases, value parser and help text (A8)."""
    name: str                      # canonical name, e.g. "terminal_height"
    aliases: tuple[str, ...]       # e.g. ("filetype", "ft", "language", "lang")
    parse: Callable[[str], object | None]   # None = invalid value
    invalid_message: str           # warn text reused by commands._set
    summary: str                   # one-line hint for usage message
```

内置 `SetOptionSpecs: tuple[SetOption, ...]` 覆盖 7 个选项（filetype 别名组 ft/language/lang；keymap；theme；shell；terminal_height——parser 内联 3..40 校验，消除与 config 校验分离的偏差；show_hidden；readonly——布尔解析函数从 commands.py `_parse_bool` 下沉为共享 `parse_bool`）。parser 一律纯函数，不 import editor。

- `commands.py:_set` 改表驱动：解析 key → 查表（含别名）→ `parse` 失败发 `invalid_message` → 成功按 `name` 分发到既有 Editor 方法/回调映射（`_APPLY: dict[str, Callable[[Editor, object], None]]`，模块级表，apply 属 L3 职责留在 commands.py）；usage 消息由 `summary` 拼接生成，消除双份文案；
- `flows/prompt_completion.py:_SET_OPTIONS` 改为 `from yate.config import set_option_names`（由 `SetOptionSpecs` 派生全部 name + aliases，含 filetype 别名组），删除手工元组；`test_prompt_completion.py:126`（补全选项名用例）自然回归。

### 3.3 守卫面

`tests/test_architecture.py` `UI_FREE_PACKAGES`（:102）追加 `"yaterc.py"`——保持 R4"session/registries/config/yaterc 不 import editor_view"守卫覆盖新文件。

### 3.4 A20 复核

`_set` 后端 setter（editor.py `set_readonly` / `set_filetype`）是 Editor 横跨 session/lsp 的操作，**不迁移**（迁移到流程模块反而制造 Editor↔flows 反向耦合）；表驱动后仅复核行数：若 `(Get-Content yate\editor.py).Count` 仍 >800，在 wave-1 plan-a 已登记的豁免名单保留并回填实测行数——此为显式偏离记录项。

## 四、新增测试与验证方案

`tests/test_set_options.py`（新增）：

1. `test_set_option_specs_cover_all_dispatched_options`——act: 解析 `SetOptionSpecs` 与 `_APPLY` 键集；assert: 两集合的 canonical name 一致（表与分发映射不漂移，A8 的"漏改则脱节"被机制化）。
2. `test_set_option_aliases_are_unique_across_specs`——act: 收集全部 name+aliases；assert: 无重复（`ft` 不得同时归属两个选项）。
3. `test_terminal_height_parser_rejects_out_of_range`——arrange: 取 `terminal_height` spec；act/assert: `parse("41") is None`、`parse("2") is None`、`parse("abc") is None`、`parse("12") == 12`（3..40 边界三点 + 类型点）。
4. `test_set_option_names_feed_prompt_completion`——act: `set_option_names()` 与 `flows/prompt_completion.py` 实际补全集合比对；assert: 逐字相等（`test_prompt_completion.py:126` 的守卫上游化）。

行为回归（既有，不改断言）：`test_action_table.py` 的 `:set` 用例 + `test_app_textual.py:3123-3133`（terminal_height 20/99/abc 三态 pilot 用例）。

验证命令（退出码 0）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_set_options.py tests/test_config.py tests/test_action_table.py tests/test_prompt_completion.py tests/test_app_textual.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
(Get-Content yate\config.py).Count; (Get-Content yate\yaterc.py).Count; (Get-Content yate\editor.py).Count
```

手工验证：启动 yate 执行 `:set`（无值）看 usage 行、`:set terminal_height=41` 与 `=12` 两态消息、`ctrl+p` 补全 `:set ` 列出全部选项名。

## 五、风险与回滚

- 风险 R2（主计划）：拆分漏改消费方 → §二.6 清单 + pyright 未解析符号必报错兜底；`_set` 表驱动改动行为回归面大 → 既有三态 pilot 用例守住。
- 回滚：config 拆分与选项表分两个提交；回滚可只退选项表（保留拆分）。
