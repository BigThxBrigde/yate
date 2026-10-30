# arch-sec-audit plan-c：CI 最小权限（S3）+ README 手册锚点与测试统计（A3）

## 输入与依据

- 取证 1（S3）：`.github/workflows/test.yml:16-40` 无顶层 `permissions:` 块
  （GITHUB_TOKEN 默认权限偏大）；action 仅 tag 锁定（`@v4`/`@v5`）。最小权限收口
  `contents: read` 即可覆盖本工作流全部步骤（checkout、pytest、pyright、changelog check）。
- 取证 2（A3）：`yate/docs/games.en.md`/`games.zh.md`/`which-key.en.md`/`which-key.zh.md`
  未被 `README.md` / `README.zh.md` / `yate/docs/README.md` 引用（仅 docs 内部互链）。
- 取证 3（A3）：`tests/README.md:16` 记载 yate/ = 140 个 .py（2026-10-17），实测 148。

## 独占文件清单（只改这些文件，不动其它任何文件）

1. `.github/workflows/test.yml`
2. `README.md`
3. `README.zh.md`
4. `yate/docs/README.md`
5. `tests/README.md`

## 具体修改

### 1. `.github/workflows/test.yml`

- 在 `on:` 块之后、`jobs:` 之前加顶层：

```yaml
# Least privilege: this workflow only checks out code and runs tests.
permissions:
  contents: read
```

- 不改 trigger、matrix、steps；Gitee 侧 `.workflow/test.yml` 不动（Go DSL 权限语义未知，
  列入 overview 非目标）。

### 2. `README.md` / `README.zh.md`（双语同步）

- 在引用 `yate/docs/` 手册清单的位置（README.md:248 附近的 docs 目录说明；先通读该区域
  再落位），补 games 与 which-key 两条链接（`yate/docs/games.en.md` /
  `yate/docs/which-key.en.md`；zh 版对应 `.zh.md`）。措辞与既有条目一致，不重排清单。

### 3. `yate/docs/README.md`

- 该文件是 docs 目录的双语索引；确认 games / which-key 两主题已列出（若缺则按既有
  条目格式补齐中英两行）。不改其它条目。

### 4. `tests/README.md`

- 第 16 行统计更新：`140` → `148`（2026-10-17 → 2026-10-29 复测）；若该行还含
  tests 文件数/用例数等数字，一并按实测刷新（用
  `(Get-ChildItem yate -Recurse -Filter *.py).Count` 与
  `git ls-files "tests/*.py" | Measure-Object` 实测取数，写进提交说明）。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q -k "manual or changelog or readme or doc" --cov-fail-under=0
python -c "print(open('.github/workflows/test.yml', encoding='utf-8').read().count('permissions:'))"
```

- 通过判定：定向 pytest exit 0（若 `-k` 零选中用例，改跑
  `pytest tests/test_manual.py -q`，文件名以实际为准）；yml 恰含 1 处 `permissions:`；
  双语 README 与 docs/README 各含 games/which-key 链接（grep 自证，写进报告）。

## 风险与回滚

- 文档 + CI 配置变更；yml 语法风险靠缩进自查与最小 diff 控制（无 actionlint，不引入新依赖）。
- 回滚 = revert 本子计划提交。
