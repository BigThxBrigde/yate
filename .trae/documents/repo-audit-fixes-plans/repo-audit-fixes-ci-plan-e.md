# 子计划 plan-k：CI 门禁补齐（A4 pyright / A14 Python 3.13 / A5-② require-zh 门禁）

> 所属波次：**wave-5**（与 test-split-plan-e 文件不重叠，可并行；子代理执行；依赖 wave-1 plan-c 清偿完毕）。
> 执行者：**子代理**（`.github/`、`.workflow/`、`tools/changelog/`、`tests/test_changelog_tool.py`，不改 `yate/`）。
> 来源：评审 A4 / A14 / A5-②；调研事实 F1（`--require-zh` 已存在但语义为全历史强制，需先修正为 released-only）。

## 一、输入

- A4：`pyproject.toml:97-99` 宣称 strict 零诊断是合并门禁，但 `.github/workflows/test.yml` 与 `.workflow/test.yml` grep `pyright` 零命中；
- A14：`test.yml:41` 固定 `'3.12'`；`requires-python >=3.12` 从未在 3.13 验证；venv 实跑环境即 Python 3.13（环境事实，`pip --version` 取证）；tree-sitter `<0.26` 上界已 pin 3.13 堆损坏（pyproject:58-62）；
- A5-②：`tools/changelog/cli.py` `check` 已支持 `--require-zh`（:296）但 CI 未传；且 `_missing_zh`（:90-93, :197）基于全历史 `entries`——未发布区段每条新提交都会挂 CI，必须先改为 released-only（与 `check` staleness 门禁 :169-177 的 released-only 语义对齐）。

## 二、独占文件清单

1. `.github/workflows/test.yml`
2. `.workflow/test.yml`（仅注释）
3. `tools/changelog/cli.py`（`_missing_zh` 拆桶 + `require_zh` 语义修正 + 输出）
4. `tools/changelog/segments.py`（如需暴露"已发布 commits"收集助手；若 `release_segments` 已含逐段 commits 则只改 cli.py）
5. `tests/test_changelog_tool.py`（新增 2 个用例）

## 三、具体修改

### 3.1 A5-②——require-zh released-only

- `cli.py`：`_missing_zh(entries, overrides)` 改为 `_missing_zh(entries, overrides, released_shas)`——`released_shas: frozenset[str]` 由 `release_segments` 中 `version is not None` 的段收集（`generate` 内构建）；`require_zh` 分支（:204-207）改为：
  - released 区段缺失 → `check failed: missing zh translations in released sections` + exit 1；
  - unreleased 区段缺失 → 打印 `warning: N missing zh in unreleased (enforced at release)`，不失败；
  - stats 输出拆分 `missing zh (released/unreleased)` 两个数字；
- 注意 `generate`（非 check 模式）的 missing 统计同样走新签名，保持一处实现。

### 3.2 A4+A14——.github/workflows/test.yml

1. `matrix` 改为（3.13 只在 Linux 腿，控制成本）：
   ```yaml
   strategy:
     fail-fast: false
     matrix:
       os: [ubuntu-latest, windows-latest]
       python-version: ['3.12']
       include:
         - os: ubuntu-latest
           python-version: '3.13'
   ```
   `Set up Python` 步骤 `python-version: ${{ matrix.python-version }}`；job name 相应带版本。
2. 新增独立 `lint` job（与 `test` 并行）：
   ```yaml
   lint:
     name: pyright (strict)
     runs-on: ubuntu-latest
     timeout-minutes: 10
     steps:
       - uses: actions/checkout@v4
         with: { fetch-depth: 0 }        # changelog gate 需要
       - uses: actions/setup-python@v5
         with: { python-version: '3.12', cache: pip, cache-dependency-path: pyproject.toml }
       - run: python -m pip install --upgrade pip
       - run: python -m pip install -e ".[dev]"
       - run: pyright --version          # 预热 npm 侧二进制
       - run: pyright                    # pyproject [tool.pyright] strict，零诊断
   ```
   （lint job 不跑 changelog gate——该门禁保留在 test job 原位。）
3. `Changelog gate` 步骤命令改为 `python -m tools.changelog check --require-zh`（test job 两腿都跑；stdlib-only，无额外安装）。

### 3.3 .workflow/test.yml（Gitee）

仅追加注释块：pyright 门禁与 3.13 腿由 GitHub 侧执行（构建机限制，评审 A4 定案）；`--require-zh` 若 Gitee 侧启用会因 overrides 领先/滞后产生误报，暂不启用——如实写明理由。

## 四、新增测试与验证方案

`tests/test_changelog_tool.py` 新增（沿用该文件既有 fixture 风格：临时 git 仓库 / 构造 entries）：

1. `test_require_zh_fails_only_on_released_missing`——arrange: 构造两个段：released（version="0.2.9"，含 commit A）与 unreleased（version=None，含 commit B），overrides 只含 B；act: 调用 `generate(check=True, require_zh=True)` 级别入口（或拆出的纯函数）；assert: 退出码 1 且输出含 "released"；互换（overrides 只含 A）时退出码 0 且输出含 unreleased warning——语义三态钉死。
2. `test_missing_zh_splits_released_and_unreleased_counts`——act: 直接调 `_missing_zh` 新签名；assert: 返回结构（或双列表）正确区分两桶，released 缺失集合不含 unreleased sha。

验证命令（退出码 0）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_changelog_tool.py -q
.venv\Scripts\python.exe -m tools.changelog check --require-zh
.venv\Scripts\python.exe -m pyright tools/
.venv\Scripts\python.exe -m pytest tests/ -q
```

- workflow 文件无法本地执行，手工验证：YAML 语法（`.venv\Scripts\python.exe -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml', encoding='utf-8'))"`，若 venv 无 pyyaml 则以 actionlint 说明替代——如实报告）；推送后首跑两条流水线观察 lint job 与 3.13 腿（此项属 CI 交互，由主代理在 wave-6 收尾确认）。
- 负向演练：本地临时清空某条 released 区段翻译（编辑 zh_overrides 的 sha 键）确认 `check --require-zh` 退出 1，再还原。

## 五、风险与回滚

- 风险 R6（主计划）：pyright runner 拉 npm 失败 → `pyright --version` 预热步 + 如实报告；R7：3.13 腿暴露兼容问题 → venv 已在 3.13 实跑，风险低，失败则 matrix 回退 include 并在 workflow 注明。
- 回滚：revert workflow 与 cli.py 两个提交；`--require-zh` flag 移除后 CI 回到现状。
