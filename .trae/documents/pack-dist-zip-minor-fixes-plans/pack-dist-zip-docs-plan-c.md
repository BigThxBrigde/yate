# 子计划 c：偏离表退出码格与 README 双语列对齐（wave-1）

> 路径基准同总纲。唯一规范来源：本文件 +
> `../pack-dist-zip-minor-fixes-plan.md` §2 +
> `../pack-dist-zip-minor-fixes-issue.md` F10/F11。

## 1. 输入与独占文件

- 现状取证：`.trae/documents/pack-dist-zip-plans/overview.md:103` 的退出码列
  填「绑定失败 / 替代路径 0」，把非零与 0 混填一格（N4）；
  `README.md:315-319` / `README.zh.md:331-335` 的示例注释起始列约
  50/50/49/49/46，视觉不成列（N5）。
- 只改三个文件：`README.md`、`README.zh.md`、
  `.trae/documents/pack-dist-zip-plans/overview.md`。
  （`tools/`、`tests/`、`pack/` 三脚本由 plan-a / plan-b 独占。）

## 2. F10：偏离表退出码格拆分

把 `overview.md` §六 表中【执行】wave-4「ps1 直接调用 `--dist release`」
那一行的退出码列由 `绑定失败 / 替代路径 0` 改为：
`1（--dist 绑定）/ 0（-Dist 与 bat）`。
其余列（实测依据、裁定）逐字保留；不改表头、其它行、§五 措辞。

## 3. F11：双语代码块注释列对齐

`README.md:314-319` 与 `README.zh.md:330-335` 的「Collect artifacts」代码块：
统一 5 行示例命令后 `#` 的起始列（选定列 41，1-based；最长命令长度 38，
故命令后补 `40 - len(command)` 个空格）。命令文本逐字保持不变：
- `.\\pack\\pack.ps1 -Dist release`
- `.\\pack\\pack.ps1 -NoZip -Dist release`
- `pack\\pack.bat --no-zip --dist release`
- `./pack/pack.sh --dist release`
- `./pack/pack.sh --no-zip --dist release`

中英两份的**命令列位、注释列位、行数**逐项一致；注释文字不改内容，只改
前置空格。不要改动代码块上方的说明行与 Note 两行；不动
`build,ts,lua` 字样；不出现本机绝对路径。

**验证探针**（可用 Python 一次性脚本，输出每个 `#` 的 0-based 索引）：
```
.venv\Scripts\python.exe -c "from pathlib import Path; [print(f, [(i+1, l.index('#')) for i,l in enumerate(Path(f).read_text(encoding='utf-8').splitlines()[313:319]) if '# ' in l and l.lstrip().startswith(('.','pack'))]) for f in ('README.md','README.zh.md')]"
```
判据：同一文件 5 行的 `l.index('#')` 完全一致；两文件对应行的列位相同。
（若探针切片行号因改动偏移，按实际行号调整，但判据不变。）

## 4. 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_spec.py -q
.venv\Scripts\python.exe -m tools.changelog check
git diff --check
```
三条退出码 0；加上第 3 节探针的「列位一致」判据才算完成。
`test_pack_spec.py` 的 `_EXTRA_HINT_FILES` 守卫会检查 README 双语的
`build,ts,lua` 字样，破坏即失败。

## 5. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 补空格触发尾随空白 / diffcheck | 空格在 `#` 之前非行尾；`git diff --check` 实测 | 还原空格 |
| 中英列位不一致 | 探针同时输出两文件并对齐判据 | 重新对齐 |
| 误改示例命令文本 | 命令逐字保留，diff 复核 | `git revert` |

回滚：`git revert` 本波提交，与 plan-a / plan-b 独立。
