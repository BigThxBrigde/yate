# plan_C：yaterc `screen_saver` 字典配置

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
  `language_servers` 式专用提取，未加进 `_KNOWN_OPTIONS`，见主方案 §八）**
- 上级：[README](overview.md) / 主方案 §4.3
- 工作量：**小**｜依赖：无（可与 plan_A 并行）

## 目标

yaterc 支持字典风格的屏保配置；`YateConfig` 新增冻结 dataclass 字段；
非法值进 `config.errors` 不崩溃。

```python
screen_saver = {
    "enable": True,       # 总开关（默认 True；False = 完全关闭，含快捷键）
    "interval": 120,      # 无输入自动触发秒数；0 = 仅手动 Alt+Shift+S
    "switch": 10,         # 每只精灵保底展示秒数
    "characters": [],     # 角色名白名单；空 = 全部
}
```

## 改动文件清单（只改这些）

| 文件 | 动作 | 内容 |
|---|---|---|
| `yate/config.py` | 改 | `@dataclass(frozen=True) class ScreenSaverConfig`（enable/interval/switch/characters）；`YateConfig.screen_saver` 字段；`_KNOWN_OPTIONS` 增 `"screen_saver"`；`_extract_screen_saver(raw)`：非 dict 报错、未知键逐个报错、类型校验（bool/int[0–3600]/int[0–3600]/list[str]）、缺键用默认；模块 docstring 选项表增条目 |
| `tests/test_config.py` | 改 | 五用例（见验收） |

## 设计约束

- config 保持**零角色知识**：`characters` 只做 `list[str]` 类型校验；
  名单成员校验在 plan_D 的 L4 装配点用 `character_names()` 比对。
- `bool` 是 `int` 子类：interval/switch 显式排除 bool（既有
  `tab_width` 同款守卫）。

## 实施步骤

1. `ScreenSaverConfig` + 字段 + `_KNOWN_OPTIONS`。
2. `_extract_screen_saver`（对齐既有 `_extract_*` 函数形态：返回
   `(value | None, error | None)` 或按现有签名）。
3. docstring 选项表与示例同步。
4. 测试五用例。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config.py -q
.venv\Scripts\python.exe -m pyright yate/config.py
```

测试用例：① 缺省 = 默认值；② 合法 dict 四键全解析；③ 未知键 →
errors 含键名；④ 非法类型（interval="x"、enable=1、characters="mario"）
→ errors；⑤ 非 dict（`screen_saver = True`）→ errors。

## 回滚

单文件增量改动，revert 即除。
