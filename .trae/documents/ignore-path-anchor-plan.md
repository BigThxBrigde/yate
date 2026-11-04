# ignore-path-anchor 计划（Gitee issue IKSFTX）

## 一、问题

`.gitignore` 的**路径锚定取反模式**不生效：打开 yate 自家仓库时，
`yate/extensions/lib/`（被 git 跟踪的内置共享 Lua 模块目录）在 explorer、
文件管理器、quick open（Ctrl+P）、全项目搜索中全部不可见；`H`（show_hidden）
无效——`lib` 不是 dotfile，而是被 basename 级 ignore 规则命中。

## 二、根因

`yate/services/workspace.py` 的 ignore 实现只支持 basename 级 `fnmatch`：

- `_parse_ignore`（workspace.py:188）解析时丢弃 `!` 前缀与结尾 `/`，
  但**不识别锚定语义**：含中缀 `/` 的模式（如 `yate/extensions/lib`）与
  前导 `/` 的模式（如 `/site`、`/_*.py`）一律按 basename 匹配；
- `_is_ignored`（workspace.py:246）匹配输入是条目 basename，多段模式
  永远无法命中 → 取反永不生效。

受影响的同类规则（仓库根 `.gitignore`）：`!yate/extensions/lib/`、
`!tools/release/`、`!tools/yxp/example/hello_yxp/manifest`、`!pack/*.spec`、
`/_*.py`、`/_*.svg`、`/site`（后三类为前导 `/` 锚定，现状同样失效）。

消费方（同一 `_is_ignored` 过滤链）：explorer `list_dir`、file manager
`list_dir`、quick open `walk_files`（palette.py）、全项目搜索
`walk_files`（find_replace.py）。

## 三、方案

gitignore 锚定语义：模式在开头或中间含 `/` 时，按**相对 ignore 文件
所在目录的路径**匹配；否则按 basename 在任意深度匹配。

### 改动 1：`_IgnorePattern` 增加 `anchored` 字段

- `_parse_ignore` 在剥离 `!` 前缀与结尾 `/` 后判定：
  `anchored = "/" in line`（先判再剥前导 `/`，剥后为空则跳过）。

### 改动 2：`_is_ignored` 签名改为接收条目完整路径

- 签名 `(name: str, ...)` → `(path: Path, ...)`；
- 根级 anchored 模式：懒计算 `path.relative_to(self.root).as_posix().lower()`
  作为匹配输入（懒计算保住 1500 层深链测试的线性复杂度——空模式表时
  不做 relative_to）；路径不在 root 之下（file manager 浏览外部目录）
  时 ValueError → anchored 根规则跳过，basename 规则维持原行为；
- 目录级模式：被检条目恒为直接子项，相对路径即 basename，
  统一按 name 匹配（含中缀 `/` 的目录级锚定模式对单段名字天然不命中，
  与 git 对直接子项的语义一致）；
- 最后命中者胜（last match wins）语义不变。

### 改动 3：锚定通配的段数守卫 `_anchored_match`

`fnmatch` 的 `*` 会跨越 `/`，而 git 的 `*` 不跨段。模式不含 `**` 时，
先要求 `rel` 与 pattern 的 `/` 段数相等再做 fnmatch（`pack/*.spec`
不再误吞 `pack/sub/x.spec`，`/_*.py` 只命中根层）；含 `**` 时退化为
普通 fnmatch（文档化近似）。保持现有 fnmatch 技术栈，不引入 `re` 翻译。

### 已知简化（与既有实现同档，文档化即可）

- 每目录 ignore 文件仍只作用于其直接子项（不沿祖先层级累积）——
  既有限制，不在本任务扩面；
- anchored 模式中的 `**` 按普通 fnmatch 处理（可跨段）。

## 四、波次

| 波次 | 内容 | 文件 |
|---|---|---|
| a | workspace.py 修复 + 测试 + 真仓库回归用例 | `yate/services/workspace.py`、`tests/test_workspace_filter.py` |

单波自包含，无并行面。

## 五、测试计划（tests/test_workspace_filter.py）

1. `parse_ignore` 既有 3 元组断言升级为 4 元组（含 anchored），补
   锚定判定用例（中缀 `/`、前导 `/`、basename 不锚定）；
2. 锚定取反复活被跟踪目录：`lib/` + `!yate/extensions/lib/`，
   `yate/extensions/lib` 及其文件在 `list_dir` / `walk_files` 可见，
   其他同名 `lib` 目录（如 `build/lib`）仍被隐藏；
3. 前导 `/` 锚定只命中根层（`/_*.py` 隐藏根层 `_x.py`、不隐藏
   `sub/_x.py`）；`/site` 类根锚定可见性；
4. 锚定取反复活文件（`*.spec` + `!pack/*.spec`）；
5. 段数守卫：`pack/*.spec` 不命中 `pack/sub/x.spec`；
6. 目录级 dir_only 锚定模式对文件不命中；
7. root 之外目录的 `list_dir` 不因 anchored 模式崩溃（file manager
   浏览外部路径）；
8. 真仓库回归：以仓库根为 Workspace root，`list_dir(yate/extensions)`
   含 `lib`（直接编码 issue 场景）。

## 六、验收命令

```
python -m pyright yate/ tests/ tools/
python -m pytest tests/test_workspace_filter.py -q
python -m pytest tests/ -q -n auto
python -m pytest tests/test_architecture.py -q
python -m tools.smoke_test run && python -m tools.smoke_test compare
```

smoke 注意：修复使 `tools/release/`、`yate/extensions/lib/` 等被跟踪
条目重新可见，若 smoke 场景截到 explorer 树并出现**预期内**基线漂移，
按约定重新注册基线并在执行记录中说明。

## 七、回滚

单 commit 改动，`git revert` 即可；无数据/配置迁移。
