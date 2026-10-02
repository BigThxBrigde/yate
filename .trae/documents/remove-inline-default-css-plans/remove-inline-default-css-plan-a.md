# remove-inline-default-css plan-a：load_tcss 进程级缓存（wave-1）

> 总纲见 [overview.md](overview.md)。独占文件清单：`yate/paths.py`、`pyproject.toml`。

## 一、目标

`yate.paths.load_tcss` 满足 issue 第 3 点"只加载一次、消费时从内存获取"：
每个样式表每进程至多读盘一次，重复调用返回内存中同一字符串。

## 二、具体修改

### 1. `yate/paths.py`

- 导入区（stdlib 组，字母序）新增：

  ```python
  from functools import lru_cache
  ```

- `load_tcss`（`yate/paths.py:54`）加装饰器，签名与 fail-fast 行为不变：

  ```python
  @lru_cache(maxsize=None)
  def load_tcss(name: str) -> str:
  ```

- `load_tcss` docstring 两处更新：
  - *name* 说明由"shell 的 `app.tcss` + screensaver 的 `screensaver.tcss`"
    改为"`app.tcss`（外壳）+ 每个 widget 类一个 `<class>.tcss`（组件样式）"；
  - 追加缓存语义一句：Results are cached in-process — each stylesheet is
    read from disk at most once per Python process; later calls are served
    from memory（异常不入缓存，缺资源每次都会 fail-fast）。
- 模块 docstring（`yate/paths.py:13-19`）的消费者清单同步：
  "the shell's ``app.tcss`` and the screensaver's ``screensaver.tcss``"
  → "every Textual stylesheet ships as a bundled ``.tcss`` under
  ``yate/resources`` and is read through :func:`load_tcss` (the shell's
  ``app.tcss`` plus one ``<class>.tcss`` per widget class -- one public
  loader so every consumer shares the same fail-fast and
  single-read-per-process contract)"。

### 2. `pyproject.toml`（仅注释，`pyproject.toml:113-116`）

`resources/app.tcss` → `resources/*.tcss`（该注释为列举性质，机制本就是
hatchling 自动整包收集，新 tcss 无需登记）。

## 三、新增测试

无（plan-c 统一落守卫：`test_load_tcss_returns_cached_string` 依赖本计划）。

## 四、验收命令（worktree 根执行）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
```

通过判定：pyright 零诊断（exit 0）、pytest 全绿（exit 0）。
另做一次导入探针（验证装饰后行为不变）：

```powershell
.venv\Scripts\python.exe -c "from yate.paths import load_tcss; a = load_tcss('app.tcss'); b = load_tcss('app.tcss'); print(a is b, len(a))"
```

预期输出 `True <字符数>`。

## 五、提交

`refactor(paths): cache bundled tcss reads in-process`
