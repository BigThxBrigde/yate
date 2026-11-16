# Gitee issue 文本草稿（待建，无编号/URL）

> 本文件是闭环流程【方案】阶段产出的 issue 文本，可直接粘贴到 Gitee 新建 issue。
> 标题建议：`ENH - Unify option definitions: one spec table for yaterc loading and :set`。
> 标签建议：`enhancement` / `refactor`。编号、URL、创建时间由 Gitee 建单后回填。

## 一、背景与现状

配置相关的三个文件是一套**单向职责流水线**，不是三份重复的 options：

| 文件 | 职责 | 依赖方向 |
|---|---|---|
| `yate/config.py` | 配置数据模型（`YateConfig` 等 dataclass）与 `:set` 选项表 | 最底层，被约 50 处 import |
| `yate/yaterc.py` | yaterc 文件发现、信任门控与 exec 加载循环 | → `yaterc_options.py` → `config.py` |
| `yate/yaterc_options.py` | 从 exec 后的 namespace 抽取并校验选项值 | → `config.py` |

其中 `config.py` 用 `SET_OPTION_SPECS`（L299-370）统一了 `:set` 命令侧：命令分派（`commands.py:36-40,429-460`）与命令行补全（`commands.py:216-237`）都从这张表派生，审计 A8 已消除该侧的双份维护。

**但 yaterc 加载侧没有纳入这张表**：`yaterc_options.py::_extract_options`（L467-599）用一份内联的 `if isinstance(...)` 链独立校验 13 个标量选项，选项名来自 `config.py:34` 的 `KNOWN_OPTIONS`。于是同一选项的「合法值 / 范围 / 报错文案」在两处各写一遍。

## 二、痛点

以下重复是实测取证，均已落到具体行号：

1. **`terminal_height` 范围写两遍**：`config.py:287` 的 `_parse_terminal_height` 用 `_parse_int_in_range(value, 3, 40)`；`yaterc_options.py:520-532` 又写 `3 <= terminal_height <= 40`。两边阈值各自维护，改一边就会漂移。
2. **8 个选项双侧重复定义**：`keymap` / `theme` / `shell` / `terminal_height` / `show_hidden` / `support_mouse` / `which_key` / `which_key_auto` 同时在 `SET_OPTION_SPECS`（`config.py:299-370`）与 `_extract_options`（`yaterc_options.py:471-594`）各维护一份校验与报错文案。
3. **选项名三份枚举**：`KNOWN_OPTIONS`（`config.py:34-39`，14 项）、`_extract_options` 里由它生成的 `options` 字典（`yaterc_options.py:469`）、`SET_OPTION_SPECS`（`config.py:299`，10 项）。新增选项要改多处才不会漏。
4. **布尔语义两套写法**：`:set` 侧把字符串经 `config.py:223 parse_bool`（`_TRUTHY` / `_FALSY`）解析；yaterc 侧直接在 `yaterc_options.py:534-568` 写 `isinstance(value, bool)`。两侧输入形态不同（命令行字符串 vs Python 原生值）本属正常，但「哪个选项是 bool」这一元信息目前散落两处。
5. **补全候选硬编码**：`commands.py:223-233` 的 `_make_set_completer` 又写了一份 `keymap=("vsc","vim")` 等 value 候选，与合法值定义脱钩。

**后果**：新增选项或调整合法范围时，必须手动同步 `:set` 表、yaterc 校验、补全候选三处；任何一处漏改都会造成「命令行能设、配置文件报错」或范围不一致，且没有守卫能提前发现。这是可维护性缺陷，不是运行期 bug。

## 三、期望行为 / 目标

1. 建立**一张选项定义表**，作为「选项知识」的唯一来源：每个选项一行，声明规范名、别名、合法值/范围、两类输入（yaterc 原生值 / `:set` 字符串）的解析方式、报错文案与 `:set` 摘要。
2. `KNOWN_OPTIONS`、`SET_OPTION_SPECS`、`set_option_names()` 等公共名**全部保留**，改为从这张表派生；外部 import 与插件可见面零变化。
3. `yaterc_options.py::_extract_options` 改为**遍历这张表**做校验与写回，删除内联的逐选项 `if` 链；`terminal_height` 的 `3..40` 之类范围只出现一次。
4. `commands.py` 的 `:set` 分派与补全候选从同一张表取合法值，消除硬编码候选。
5. 新增**防漂移守卫**，钉住「两侧校验同源」：任何一侧重新出现硬编码范围/合法值，或表与派生视图不一致，架构测试即失败。

## 四、验收标准

- [ ] `config.py` 中存在一张统一选项表，`:set` 表与 `KNOWN_OPTIONS` 均由它派生；两处不再各自硬编码选项名清单。
- [ ] `terminal_height` 的 `3..40`、`keymap` 的 `vsc|vim`、`yate_trace_level` 的等级集合等合法值/范围在 `yate/` 内各只有一处声明。
- [ ] `yaterc_options.py::_extract_options` 不含逐选项的 `if isinstance(...)` 校验链，改为通用遍历；dict / list 类选项（`screen_saver` / `file_preview` / `large_file` / `language_servers` / `extensions` / `theme_dirs` / `disabled_extensions`）的既有 extractor 保持不变。
- [ ] 既有测试全绿：`tests/test_set_options.py`、`tests/test_yaterc_options.py`、`tests/test_config.py` 的断言无需放宽即可通过。
- [ ] 新增守卫覆盖：表 ↔ 派生视图一致性、范围单一来源（含反例演练：写回硬编码范围须令守卫失败）。
- [ ] 用户可见行为不变：合法值、默认值、报错文案、`:set` 报错文案、补全候选集合与加载顺序均与改动前一致。
- [ ] 全量门禁退出码 0：`pyright` 零诊断、`pytest tests/ -q -n auto`、架构测试、`--cov-fail-under=75`、冒烟。
- [ ] `config.py` 与 `yaterc_options.py` 均保持 800 行阈值内（当前 378 / 742 行）。

## 五、边界与兼容性

- 三文件的职责分工**保持不变**（数据模型 / 加载器 / 校验器），本 issue 只收敛「选项定义」这一横切知识，不合并文件、不新增层级。
- `YateConfig` 等 dataclass 是公共面，字段、默认值、类型一律不改。
- yaterc 加载顺序、信任门控、主题回调注入（`register_theme` / `load_theme_paths`）不改。
- 两侧输入形态差异保持：yaterc 接原生 Python 值（bool 必须写 `True` / `False`），`:set` 接字符串（`on` / `off` / `true` / `false` / `1` / `0` / `yes` / `no`）。统一的是「定义」，不是把两种输入强行归一。
- 全部模块仍为 L0 UI-free 叶面（R4 / R12）：不 import `editor_components` / `textual.app`。

## 六、非目标

- 不合并 `config.py` / `yaterc.py` / `yaterc_options.py` 三个文件。
- 不改动 `:set` 的 `SET_APPLY` 副作用映射（属 L3 命令层职责）。
- 不收敛 dict / list 类选项的复杂 extractor 逻辑（它们没有跨两处重复）。
- 不新增配置项、不新增 `:set` 别名、不改变任何报错文案与默认值。
- 不改双语手册语义；仅在文档需说明「定义唯一来源」时补充一句实现说明。

## 七、需同步的文档

- 方案与评审记录：`.trae/documents/option-spec-unify-plans/overview.md` 及各子计划。
- 若实现中触碰架构守卫面：`architecture-boundaries.md` §一 L0 清单 / R4 / §六 与 `tests/test_architecture.py`（本方案设计为**不触碰**，见总纲「架构边界影响」）。
- 双语手册 `yate/docs/yaterc.en.md` / `yaterc.zh.md` 的选项表：行为不变则无需改；实现完成后复核一遍。
- `CHANGELOG.md` / `CHANGELOG.zh.md`：按项目惯例在合并前补记「internal refactor, no behavior change」。
