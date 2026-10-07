# plan-d：文档与全量门禁

> 总纲见 `overview.md`。前置依赖：plan-a/c 落定的键名与默认值语义。

## 一、目标

双语手册同步 `file_preview` 配置项（硬约束）、配置样例更新、
顺带补 manual 的 palette 段落一句，然后跑收尾全量门禁。

## 二、独占文件清单

- `yate/docs/yaterc.en.md`（改）
- `yate/docs/yaterc.zh.md`（改）
- `yaterc.example`（改）
- `yate/resources/manual.en.md`（改，一句话）
- `yate/resources/manual.zh.md`（改，一句话）

## 三、逐文件改动明细

### `yate/docs/yaterc.en.md` / `yaterc.zh.md`

- 在 `screen_saver` 小节之后新增 **file_preview** 小节（双语内容对齐，en/zh
  各自成段，结构互为镜像）：
  - 键表：`enable`（总开关，默认 True；False 时 Ctrl+P 与旧行为一致）、
    `position`（`right`/`left`，预览窗格方位）、`size`（预览占 palette 宽度
    百分比 10-80，默认 40）、`max_lines`（读取/高亮行数上限，默认 2000，
    超出截断并提示）、`max_size`（字节上限，默认 1 MiB，超出不读只提示）；
  - 示例代码块（与 plan-a docstring 示例一致）；
  - 一句行为说明：预览按文件类型自动语法高亮；二进制文件与大文件降级提示；
  - 引用既有「语法色板」小节（syn_* 颜色来自主题）。

### `yaterc.example`

- 在 `screen_saver` 注释块之后补 `file_preview` 注释样例
  （风格对齐既有条目：`#` 注释 + 键值 + 行尾说明）。

### `yate/resources/manual.en.md` / `manual.zh.md`

- §3.8（en 304-309 行附近，zh 对应章节）"Ctrl+P opens quick open" 条目后
  追加一句：预览窗格随光标显示文件内容与语法高亮，`file_preview` 可配置
  （en/zh 同步）。若 zh 行号漂移，按章节标题 `3.8` 定位，不按行号。

## 四、架构边界自检

- 文档相对路径引用（doc-conventions §五）：新增内容引用代码标识符用
  行内代码，不引入绝对路径 ✓
- 双语成对更新（§三：同时新增、同时更新）✓
- 根级文件名不动 ✓

## 五、验收命令

纯文档 + 已验证代码，本波门禁即收尾门禁（worktree 内）：

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/
.venv\Scripts\python.exe -m pytest tests/ -q
```

预期：pyright 零诊断；pytest 全绿（含 test_architecture 22 用例）；
覆盖率 `--cov-fail-under=75` 由审核环节以全量命令复核：

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-fail-under=75
```

冒烟：plan-e 已注册 3 条 preview 场景（渲染/截断/关闭），本波收尾跑全量
smoke 复核（含既有场景无回归）：

```powershell
.venv\Scripts\python.exe -m tools.smoke_test
```

## 六、回滚

纯文档回退无风险；门禁失败则按 overview §七 风险表处理。
