# 子计划 f：README 与应用内手册双语同步（wave-3）

> 路径以本文件所在目录为基准：`../../../README.md` 等即仓库根对应文件。
> 唯一规范来源：本文件 + `../pack-dist-zip-plan.md` §1 范围裁定 + `overview.md`。
> 前置：wave-2 三脚本已落盘；与 plan-b 同波并行（文件互不重叠）。

## 1. 输入与范围裁定

- `../../../README.md:305-314` / `../../../README.zh.md:321-330`：构建段落只列
  `pack.ps1` / `--onefile`，无 `--dist`、无 zip 说明。
- `../../../yate/resources/manual.en.md:1650-1671` /
  `../../../yate/resources/manual.zh.md:1474-1493`：「Collect artifacts into a
  versioned directory」/「归集产物到版本目录」已详述 `--dist` 现状，并写
  「Without `--dist` the behavior is unchanged」。新增默认 zip 后若不改，手册
  与产品行为不符（`doc-conventions.md` §三 双语同步硬约束）。
- `../../../tests/test_pack_spec.py:416-443` 的 `_EXTRA_HINT_FILES` 把两个
  README 与两个手册列入「`build,ts,lua` 提示」守卫面：改这些文件时**不得**
  破坏 `pip install -e ".[build,ts,lua]"` 字样（守卫正则 `build,ts(?!,lua)`）。

## 2. 独占文件清单

只改四个文件：`../../../README.md`、`../../../README.zh.md`、
`../../../yate/resources/manual.en.md`、`../../../yate/resources/manual.zh.md`。
不得改其它文档、脚本、测试。

## 3. 具体修改（定位到行号）

1. **README.md（`:305-314` 构建代码块及其后）** 追加英文示例与说明：
   ```
   .\pack\pack.ps1 --dist release                 # collect + write release/<stage>.zip by default
   .\pack\pack.ps1 -NoZip --dist release          # collect without the zip archive
   pack\pack.bat --no-zip --dist release          # same switch through the cmd wrapper
   ./pack/pack.sh --dist release                  # Linux: zip by default
   ./pack/pack.sh --no-zip --dist release        # Linux: skip the zip
   ```
   并在代码块后补 2-3 句：成功归集后默认生成同名 zip（zip 内顶层保留
   stage 目录）、`<dist>/SHA256SUMS.txt` 追加该 zip 的 SHA256、stage 保留、
   `--no-zip` 跳过压缩且其余步骤不变。
2. **README.zh.md（`:321-330`）** 与英文逐项对齐（中文措辞，命令示例一致），
   不增删示例条数。
3. **manual.en.md（`:1650-1671`）**：在「Collect artifacts」段落的 PowerShell /
   bash 示例后补 `--no-zip` 示例与 2-3 句默认 zip 说明；把末段
   「Without `--dist` the behavior is unchanged -- only `dist/` is produced.」
   扩展为同时说明「未传 `--dist` 时无论是否带 `--no-zip` 都不产出 zip」；
   明确 `<dist>/SHA256SUMS.txt` 是 dist 根校验文件、与 stage 内同名文件语义
   不同；保留 `pip install -e ".[build,ts,lua]"`（`:1647`）原样。
4. **manual.zh.md（`:1474-1493`）** 与英文逐项对齐，保留
   `pip install -e ".[build,ts,lua]"`（`:1470` 附近）原样。
5. 四份文档都不得出现本机绝对路径 / 盘符路径（`doc-conventions.md` §五）；
   命令示例相对仓库根。

## 4. 验证方案与测试用例

| 用例 / 探针 | arrange | act | assert |
| --- | --- | --- | --- |
| 双语同步人工核对（本波） | 四份文档 | 逐段比对 README 与 README.zh、manual.en 与 manual.zh | 命令示例条数 / 参数 / zip 说明语义逐项一致 |
| `test_build_extra_hints_when_scanned_always_name_the_lua_extra`（既有用例，参数化 8 文件） | 不改 | `python -m pytest tests/test_pack_spec.py -q` | 8 个参数化用例全绿（`build,ts,lua` 字样未被截断） |
| `test_help_text_when_scripts_scanned_covers_new_switch`（plan-b） | 文档外的脚本 | 静态断言 | README 改动不影响脚本守卫 |
| changelog 门禁 | README 已改 | `python -m tools.changelog check` | 退出码 0 |
| wiki 源收集回归 | manual 已改 | `python -m pytest tests/test_pack_wiki.py -q` | 退出码 0（该测试引用 manual 文件） |

## 5. 可执行验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_spec.py tests/test_pack_wiki.py -q
.venv\Scripts\python.exe -m tools.changelog check
```

判定：退出码全 0。纯文档改动本身按 `misc-rules.md` §三 可豁免测试，但本波与
代码改动同批（最高风险判定），仍按常规跑上述命令；全量门禁由主代理收尾统一执行。

## 6. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 双语不同步 | 逐项对齐示例条数与语义；验收人工核对 | 补另一语言 |
| 误改 `build,ts,lua` 触发既有守卫 | 明确「保留原样」；跑 `test_pack_spec.py` | 恢复字样 |
| 手册章节编号 / 结构被破坏 | 只在「Collect artifacts」段落内追加，不动 §19 其它段落 | `git revert` |
| README 里写绝对本机路径 | 只用命令与相对目录 `release/` | 改相对写法 |

回滚：`git revert` 本波提交；代码功能不受文档回退影响，但会遗留文档与行为
不一致，故不作为最终状态保留。
