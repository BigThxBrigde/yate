# plan_F：全量门禁 + 主方案回填 + 提交

- **状态：已完成（2026-09-27，门禁实测与回填见主方案 §八）**
- 上级：[README](README.md)
- 工作量：**小**｜依赖：plan_A–E 全部完成

## 步骤

### 1. 全量门禁

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/   # 零诊断
.venv\Scripts\python.exe -m pytest tests/ -q              # 全绿，含 20 架构用例
.venv\Scripts\python.exe -m tools.pack rosters            # 退出 0
Test-Path .trae\documents\fancy_sym_preview               # False（临时目录已清）
```

失败修复后重跑；不豁免、不 `# type: ignore`。

### 2. 主方案回填

[../fancy_sym_plan.md](../fancy_sym_plan.md) 状态行改为"已实施"，回填：
真实测试数（基线 → 终态）、pyright 诊断数（0）、与计划的偏离点及实测
依据（如角色造型微调、尺寸变化）；子计划文件头部标完成日期。

### 3. 提交（英文 conventional，逐个落盘后再提交下一个）

```
feat(sprites): add pixel sprite pack and shuffle registry
feat(config): add screen_saver dict option (enable/interval/switch/characters)
feat(tools): add pack rosters subcommand rendering roster preview
feat(screensaver): add full-terminal screensaver screen with idle trigger
feat(actions): add toggle_screensaver action (alt+shift+s)
docs: document screensaver options
chore: drop temporary preview scaffolding
```

对应文件分组：sprites→`yate/editor_sprites/**`+`tests/test_editor_sprites.py`
+`tests/test_architecture.py`（UI_FREE_PACKAGES 登记）；
config→`yate/config.py`+`tests/test_config.py`；tools→`tools/pack/**`；
screensaver→`editor_view/screensaver.py`+`services/idle_tracker.py`+`app.py`
+`tests/test_screensaver.py`+`tests/test_idle_tracker.py`；actions→
`actions.py`+`keymaps/*`；docs→README×2+yaterc×2+resources changelog×2
+根 CHANGELOG×2；chore→删除的临时预览目录。

### 4. 完成判据

- [ ] 门禁三条全过；
- [ ] 主方案与全部子计划已回填；
- [ ] 临时目录不存在；
- [ ] 提交序列落盘，工作区干净。
