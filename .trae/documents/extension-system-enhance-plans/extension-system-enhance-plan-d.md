# plan-d — 文档 / 示例 / 冒烟 / CHANGELOG（wave-3）

父计划：[../extension-system-enhance-plan.md](../extension-system-enhance-plan.md)

前置：wave-1（plan-a）、wave-2（plan-b ∥ plan-c）验收全绿。

## 目标

双语手册同步记载新 API 面，示例模板演示新能力，冒烟覆盖 UI 贡献点，
CHANGELOG 双语登记。

## 改动文件（独占清单）

| 文件 | 动作 |
|---|---|
| `yate/docs/extensions.en.md` / `extensions.zh.md` | 新增 "Events" / "Status bar segments" 两节；Lua 节补 setup/teardown 写法与注解说明；双语同步 |
| `yate/extensions/example_ext.py.example` | 补事件订阅 + 状态栏段示例（含退订演示） |
| `yate/extensions/lua.example` | 补显式 setup/teardown 写法（保留顶层兼容演示） |
| `tools/smoke_test.py` | 新增场景 `extension_status_segment`（临时扩展注册段→断言状态栏文本） |
| `tools/smoke_baselines/*.json` | `snapshot` 重新生成（新增场景） |
| `CHANGELOG.md` / `CHANGELOG.zh.md` | Unreleased 登记：events / ui segments / lua hooks / lua 包分层 |

## 步骤

1. 手册双语（先 en 后 zh 同步翻译；路径引用相对化，遵守 doc-conventions §五）。
2. 示例模板更新（代码内注释英文，misc-rules §四）。
3. smoke 场景 + snapshot 基线重生成；`run` 与 `compare` 各跑一遍。
4. CHANGELOG 双语。
5. 核对手册中测试计数引用（若被本任务改动文件涉及则同步为实测值）。

## 验收命令

```text
.venv\Scripts\python.exe -m tools.smoke_test run
.venv\Scripts\python.exe -m tools.smoke_test compare
python tools\check_docs_links.py        # 若存在该脚本则以实际名为准；不存在则跳过
.venv\Scripts\python.exe -m pytest tests/ -q
```

（纯文档步骤本身按 misc-rules §三豁免测试；本子计划含 smoke 脚本与示例
改动，仍跑 smoke 与全量 pytest。）

## 回滚

文档/示例/基线文件逐个 revert；smoke 场景回退不触运行时。
