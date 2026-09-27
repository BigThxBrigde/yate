# plan_E：文档（yaterc / README / CHANGELOG）

- 上级：[README](README.md)
- 工作量：**小**｜依赖：plan_A–D 全部完成

## 目标

用户可从文档发现并配置屏保；版权署名落盘（主方案 §2.4）。

## 改动文件清单（只改这些）

| 文件 | 内容 |
|---|---|
| `yate/docs/yaterc.en.md` | `screen_saver` 字典示例 + 四键说明表 |
| `yate/docs/yaterc.zh.md` | 同上（中文） |
| `README.md` | Features 增 "Screensaver mode" 小节：`Alt+Shift+S`、空闲触发、27 角色、yaterc 示例；`Inspired by Joel Yliluoma's "that_editor" (https://github.com/bisqwit/that_editor)` 署名；注明角色为致敬性原创近似绘制 |
| `README.zh.md` | 同上（中文） |
| `yate/resources/changelog.en.md` | Unreleased 增英文条目（feat 屏保 + tools.pack rosters + 配置），含署名（嵌入式 changelog，`show_changelog` 查看器读它） |
| `yate/resources/changelog.zh.md` | 同上（中文） |
| `CHANGELOG.md` | 同步英文条目（根目录镜像，v0.2.6 起惯例） |
| `CHANGELOG.zh.md` | 同步中文条目 |

## 实施步骤

1. yaterc 双语文档（放既有选项表之后）。
2. README 双语（截图占位：可跑 `.venv\Scripts\python.exe -m tools.pack
   rosters` 生成 roster.svg 附入 docs，可选）。
3. CHANGELOG 条目。

## 验收

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q        # 文档不破坏任何测试
```

人工检查：三份文档示例可直接粘贴进 yaterc 生效（字典冒号语法）；
署名出现在 README×2 与 CHANGELOG。

## 回滚

纯文档，revert 即除。
