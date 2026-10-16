# plan-e：集成测试与全量回归（wave-4）

> 总纲见 [overview.md](overview.md)。波次：wave-4；依赖 plan-a–d 全部
> 落地。测试文件不计改动判据，但本波是**跨子计划行为的集成验收层**。

## 一、输入

- plan-a（engine 原语）、plan-b（confirm 循环）、plan-c（Screen 组件）、
  plan-d（接线）的全部交付物与其波内测试（已各自绿）；
- 本波只补**跨波交互**用例与负向路径，不重复波内已覆盖的单元行为。

## 二、独占改动文件清单

| 文件 | 动作 |
|---|---|
| `tests/test_app_find_replace.py` | 追加接线后集成用例（plan-c 创建、plan-d 追加过 5 条；本波继续追加，串行独占） |
| `tests/test_app_find.py` | 仅在 plan-b 用例有遗漏时补漏（默认不动） |

## 三、新增用例（详细三要素）

追加 `tests/test_app_find_replace.py`：

| 用例 | 前置与操作 | 断言 |
|---|---|---|
| `test_project_replace_end_to_end_open_edit_replace` | tmp_path workspace 三文件各含 needle；ctrl+h 打开；输入 find/replace；`a`；escape；enter 前先打开文件 1 | 全部文件落盘正确；已打开文件 buffer 换且 dirty；消息含 replaced 统计 |
| `test_project_replace_enter_jumps_to_match_row_col` | 单文件多行多匹配；ctrl+h → 输入 → 结果区 down 到第 2 匹配 → enter | 打开文档 `buffer.cursor` == 第 2 匹配 `(row, end)`；视图滚动至可见（`reveal_cursor` 后可见性断言） |
| `test_ctrl_h_from_search_prompt_state_recovers` | 先 `/needle` 进入 live search（prompt 激活）；escape；再 ctrl+h | Screen 正常打开；关闭后 prompt 行为正常（无悬挂 `on_key` 钩子） |
| `test_f4_confirm_loop_then_ctrl_h_coexist` | F4 confirm 循环做到一半 `q` 退出；再 ctrl+h 打开 Screen | Screen 打开成功；confirm 状态字段已清（`_confirm_total == 0`） |
| `test_project_replace_readonly_open_doc_refuses` | read-only 已打开文档含 needle + 正常文档；`a` | read-only 文档未变且 readonly 提示出现；正常文档已替换 |
| `test_project_replace_regex_option_end_to_end` | 文件含 `a@x b@x`；`alt+r` 开正则；find `(\w+)@x`、repl `\1`；`a` | 磁盘内容 `"a b"`（backreference 逐匹配语义贯通三层） |
| `test_unmatched_printable_keys_fall_through_in_screen` | Screen 打开、焦点在结果区；`press "z"` | 无异常、无替换、游标不动（R10 fall-through） |
| `test_f4_no_matches_then_replace_all_still_works` | F4 输入无匹配 query → warn；再 F4 输入有匹配 query → `a` | 第二次循环正常替换（warn 后状态无残留） |

负向路径（异常流）已由 plan-b/c 波内用例覆盖：read-only（b、c 各一）、
二进制/超限（c）、无 workspace（d）。本波不重复。

## 四、验证方案

| 目标 | 命令 | 通过判定 |
|---|---|---|
| engine 行为与边界 | `.venv\Scripts\python.exe -m pytest tests/test_project_search.py tests/test_editor_core.py -q` | 退出码 0 |
| confirm 循环全路径 | `.venv\Scripts\python.exe -m pytest tests/test_app_find.py -q` | 退出码 0 |
| Screen + 接线集成 | `.venv\Scripts\python.exe -m pytest tests/test_app_find_replace.py -q` | 退出码 0 |
| 架构守卫（31 用例 + 本轮新文件自动面） | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 退出码 0 |
| 全量回归 | `.venv\Scripts\python.exe -m pytest tests/ -q` | 退出码 0 |
| 类型门禁 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | 零诊断 |

无法自动化的部分（真实终端 ctrl+h 键序、主题切换视觉、`.gitignore`
深层目录行为）按总纲 §八手工清单执行，由执行者在收尾汇报记录结果。

## 五、风险与回滚

- 本波不改产品代码：集成用例暴露的缺陷回修属对应波次（a–d）的返工，
  按该波回滚路径处理；本波自身追加用例可独立 revert。
