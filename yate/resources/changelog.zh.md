# 变更日志

> 由 git 历史自动生成于 2026-09-14 · yate 0.2.0

## [未发布] · [compare](https://gitee.com/jermaine/yate/compare/v0.2.0...HEAD)

### 新功能

- add --dist artifact staging and require .venv interpreter [缺中文] ([`483b667`](https://gitee.com/jermaine/yate/commit/483b6679d93cc0773390887dfc38f3bc9716a620))
- Fix failed unit tests [缺中文] ([`5b03805`](https://gitee.com/jermaine/yate/commit/5b0380563819be1434e38f3c1dd835ca52a98695))

### 文档

- release v0.2.0 bilingual changelog [缺中文] ([`3507664`](https://gitee.com/jermaine/yate/commit/350766418f03484744f3522749e847d68932a949))

## [0.2.0] - 2026-09-14 · [compare](https://gitee.com/jermaine/yate/compare/v0.1.1...v0.2.0)

### 新功能

- 新增 --setup-defaults/--cleanup-defaults 一键初始化与清理用户配置目录 ([`04ec16e`](https://gitee.com/jermaine/yate/commit/04ec16ea59bcc748b39ca78d1aaf3b1de9675c73))
  - 模板以 .example 原后缀发放、改名 .py 才激活；cleanup 需确认且默认保留 data/；新增 crash.uninstall 解决 Windows 句柄占用

### 文档

- 文档同步一键初始化/清理命令（手册、主题与 yaterc 指南、README） ([`738c2f1`](https://gitee.com/jermaine/yate/commit/738c2f1bb22b0b14aaa62a6c683a0793a93ca459))
- 发布 v0.1.1 双语变更日志 ([`78253f0`](https://gitee.com/jermaine/yate/commit/78253f04f44ed47de8a8efbada9aee1550168422))

### 测试

- 补充用户配置初始化/清理服务层、CLI 参数透传与崩溃句柄释放测试 ([`6e77ebe`](https://gitee.com/jermaine/yate/commit/6e77ebed0050caf573d644218a070d7b0d7f3a8a))

## [0.1.1] - 2026-09-14 · [compare](https://gitee.com/jermaine/yate/compare/v0.1.0...v0.1.1)

### 新功能

- 随包附带 Dracula 与 Ayu 主题模板，复制为 *.py 后即可启用 ([`28d74c5`](https://gitee.com/jermaine/yate/commit/28d74c57076ee941bd400f358eeb4bec3ea9ac52))
- 新增 One Dark/Light 与 Gruvbox dark/light 四套内置主题 ([`a4d880b`](https://gitee.com/jermaine/yate/commit/a4d880bf2534d3e8970d2757a0631e9718148840))
  - 内置主题由 4 套扩至 8 套，默认仍为 mocha，可用 :theme 即时切换

### 问题修复

- wait for in-flight connect in stop() so spawned servers always terminate [缺中文] ([`7c69c6b`](https://gitee.com/jermaine/yate/commit/7c69c6bbece7a13691b76ab4786f1e7543a13c02))

### 文档

- 文档同步八套内置主题与模板安装方式（README、手册、主题指南） ([`26ba949`](https://gitee.com/jermaine/yate/commit/26ba949ed4a4bce041533e2308803e52d19b3fc5))
- move changelog maintenance appendix from manuals to README [缺中文] ([`33190c5`](https://gitee.com/jermaine/yate/commit/33190c5a10e073ecd5c6cccefa7ecc083d859828))
- release v0.1.0 bilingual changelog [缺中文] ([`ddcb70c`](https://gitee.com/jermaine/yate/commit/ddcb70c3f72d91e09fcac1b33eab4399e836a2f2))

### 测试

- 补充内置色板与主题模板加载测试，修复旧测试注册表泄漏与版本号硬编码 ([`a4aaa68`](https://gitee.com/jermaine/yate/commit/a4aaa68c349a4cb5c6f7bb09d9549ed26d402a1d))

### 构建与工程

- pin gitee origin so the changelog gate passes on GitHub [缺中文] ([`76518e0`](https://gitee.com/jermaine/yate/commit/76518e04a14c895507a74a854e93a9fbaa7a49ef))
- bundle tree-sitter backend and python/bash grammars in frozen builds [缺中文] ([`74202ac`](https://gitee.com/jermaine/yate/commit/74202accea55e7c6339eb060e3e11d4b29b22dbd))

## [0.1.0] - 2026-09-13 · [compare](https://gitee.com/jermaine/yate/compare/ROOT...v0.1.0)

_首个版本。_

### 新功能

- 泛化 Markdown 文档屏，新增 :changelog 命令与 --changelog 参数 ([`74c8938`](https://gitee.com/jermaine/yate/commit/74c893846406fc33f173b3cf6840ebe9047186a8))
- 双目标渲染与已发布段新鲜度门禁 ([`f78bc6e`](https://gitee.com/jermaine/yate/commit/f78bc6ef0e493a752098bdfad298f23bb6f10a30))
- 基于 git 历史的双语变更日志生成器 ([`4144a72`](https://gitee.com/jermaine/yate/commit/4144a72e2a868a64970c0a3c12f63a516f24d80f))
- 崩溃诊断持久化：经 faulthandler 写入 ~/.yate/data ([`4739dc3`](https://gitee.com/jermaine/yate/commit/4739dc3fd2b6d78024682458f74d1d8503901811))
  - native crash 与未捕获异常都会落盘为带时间戳的 .err 文件，正常退出时自动清理
- 随主题变色的滚动条与可点击标签栏 ([`5f4cc48`](https://gitee.com/jermaine/yate/commit/5f4cc48c14f30bf5ae5ceaa18e80f157f1c0107f))
- tree-sitter 语法后端，支持扩展注册语法 ([`b0f95a1`](https://gitee.com/jermaine/yate/commit/b0f95a19a5a9035b8db40889bdf4cae70cd7e575))
- declarative language_servers yaterc option auto-activates [缺中文] ([`e1615f0`](https://gitee.com/jermaine/yate/commit/e1615f088061cd435659b0d429ff55690ec31cea))
- bare-number command jumps to line and Ctrl+G prompt [缺中文] ([`4ccd904`](https://gitee.com/jermaine/yate/commit/4ccd9041726904e0629fb905067fd0649b7c3fe1))
- custom syntax highlighting via extensions + C# bundle [缺中文] ([`db82bce`](https://gitee.com/jermaine/yate/commit/db82bcea306058ac1919a42f054f971e8301129c))
- manual syntax/filetype selection like :set filetype [缺中文] ([`8e9337a`](https://gitee.com/jermaine/yate/commit/8e9337a0c8f49691dcbbe3023f08e745c9a12f7b))
- bind F5 to open the ex command line [缺中文] ([`669f017`](https://gitee.com/jermaine/yate/commit/669f017b6c32a5731db8679fa4c31f78616845b9))
- 基于 buffer 的自动补全与 bash 式 Tab 补全 ([`bcd0426`](https://gitee.com/jermaine/yate/commit/bcd04266064ae148ab4d69e96aad5e14933cd80b))
- add --theme flag and fix --theme-dir ~ expansion [缺中文] ([`5e69220`](https://gitee.com/jermaine/yate/commit/5e692204956e1b809f94a99bac08732c7661ad01))
- add in-manual search [缺中文] ([`f002de4`](https://gitee.com/jermaine/yate/commit/f002de48dbd612275b04711ad2db5c11f82cc8a6))
- show all commands and actions, searchable by full name [缺中文] ([`eb4016e`](https://gitee.com/jermaine/yate/commit/eb4016efc261c4391e7cc553de4ca8a3c4b26a77))
- custom theme directories via theme_dirs and --theme-dir [缺中文] ([`53af6de`](https://gitee.com/jermaine/yate/commit/53af6defaff10e126c31c805904d0e2da40a1d3e))
- 集成终端面板（PTY 驱动），快捷键开关 ([`ee7cd53`](https://gitee.com/jermaine/yate/commit/ee7cd5323555bb7309a2fc41405911863e4cacb3))
- LSP 支持：自动补全与诊断 ([`ad28ef5`](https://gitee.com/jermaine/yate/commit/ad28ef5fb3963d6798833d4ae53d577a00c4617c))
- 键位：资源管理器与编辑器间的窗口切换 ([`8cd80b2`](https://gitee.com/jermaine/yate/commit/8cd80b26cf389d6a713fd361c079f59d138e2748))
- 双语用户手册（英/中），打开时套用主题，修复表格布局 ([`a819973`](https://gitee.com/jermaine/yate/commit/a819973a7d943be31df221ae10f549f6d3f1654b))
- 内置只读用户手册查看器（F8 / :manual） ([`88d6b52`](https://gitee.com/jermaine/yate/commit/88d6b52e1ddeb789c5eb7e4776ed3d5d4e32fd1a))
- banner in ANSI Shadow figlet style [缺中文] ([`2cf85a1`](https://gitee.com/jermaine/yate/commit/2cf85a113005dc140697ffe1d1eaf5176d2fcf6a))
- switch command palette to alt+shift+p [缺中文] ([`ba6d7a6`](https://gitee.com/jermaine/yate/commit/ba6d7a6a3852132fbcc5f7d498eb896de2975c88))
- 随包捆绑 JetBrains Mono Nerd Font；修复 Windows Terminal 配置覆盖 ([`d2ce815`](https://gitee.com/jermaine/yate/commit/d2ce8158eba4619836b41ec067b810a752842556))

### 问题修复

- 防护 tree-sitter 0.26 在 Windows 上的堆内存损坏 ([`85cb9ad`](https://gitee.com/jermaine/yate/commit/85cb9ad740f2a218f16c5e5c50e67a6d3612d144))
- 修复 Windows CI 竞态：停止期间的 LSP 子进程与 8.3 短路径 ([`3f4c4db`](https://gitee.com/jermaine/yate/commit/3f4c4dbc43144b89b6fcedf964bee7ec66758543))
- LSP didChange 同步重试、扩展卸载钩子与打包规格跟踪 ([`6cf4fea`](https://gitee.com/jermaine/yate/commit/6cf4fead2daea53083300332eb96751e2bc5c4f7))
- 修复 :q 始终退出；按文件启动时隐藏资源管理器 ([`1a4e493`](https://gitee.com/jermaine/yate/commit/1a4e493e3685bf06f7ae4e82f5f0d3b3ffc26b24))
- 修复关闭窗格命令、按键冲突、手册搜索与中文字形 ([`e70dd15`](https://gitee.com/jermaine/yate/commit/e70dd15505ef4e5116390d752e0154e0f1e5389a))
- dismiss the welcome page on :enew and never re-show it [缺中文] ([`8477ec0`](https://gitee.com/jermaine/yate/commit/8477ec06c5269088923f0958098460bfce96b2d4))
- accept the real Ctrl+grave key names so the panel closes [缺中文] ([`9ea2ac5`](https://gitee.com/jermaine/yate/commit/9ea2ac5fc4a02fa375797c8a42b83b4f4b9e4fd7))
- tear down background services cleanly so quitting never prints tracebacks [缺中文] ([`f0da8b2`](https://gitee.com/jermaine/yate/commit/f0da8b286d113d46d550c983ef88a305110983e5))
- only open ex command prompt from ":" in vim mode [缺中文] ([`9b76ae4`](https://gitee.com/jermaine/yate/commit/9b76ae4ccc8be426d2706577a9447fe94a9e0e9b))
- preserve early PTY output when panel lays out after spawn [缺中文] ([`3ca822c`](https://gitee.com/jermaine/yate/commit/3ca822c663403214336b33575d6a452683e8d1b5))
- explicit theme backgrounds; keyboard-driven file explorer [缺中文] ([`27b267c`](https://gitee.com/jermaine/yate/commit/27b267cbb99d135319eefaad64eba2c3e3132275))
- viewport follows cursor and buffer can scroll [缺中文] ([`e28de3c`](https://gitee.com/jermaine/yate/commit/e28de3c09b649cfe90ac4ed280b9168d8efbb6f6))
- Nerd Font icons, prompt echo, duplicate tab row; welcome banner [缺中文] ([`bf2b06a`](https://gitee.com/jermaine/yate/commit/bf2b06a99c13fa63e8fa4d84ab8c0ce11f9aa8d8))

### 性能优化

- 移动光标时保持语法配色 ([`2b8b737`](https://gitee.com/jermaine/yate/commit/2b8b73748ef182dbf3921b65a51e8788331247a1))
- 阻塞操作移入后台线程，保持界面流畅 ([`fd48e3c`](https://gitee.com/jermaine/yate/commit/fd48e3cb6d14a20b129ab1e328f35fe1502731ed))

### 重构

- rename controllers to app_features, explorer_files to explorer [缺中文] ([`94d78c0`](https://gitee.com/jermaine/yate/commit/94d78c08400d9ea022e89ec6d1df80bd1bbd1e66))
- rename app_parts to controllers, drop *_ops module names [缺中文] ([`e5f847b`](https://gitee.com/jermaine/yate/commit/e5f847b4d825311a5f5ba9db280e589d3d991e7a))
- extract YateApp collaborators into yate.app_parts [缺中文] ([`26076fd`](https://gitee.com/jermaine/yate/commit/26076fd856ee115ccb109ed084347f5cb5b27bcd))

### 文档

- README 与手册补充变更日志入口 ([`2490bb3`](https://gitee.com/jermaine/yate/commit/2490bb3301edaab5693f2e508126d184d2782faf))
- 生成 v0.1.0 双语变更日志并接入发布工作流 ([`fc74d5f`](https://gitee.com/jermaine/yate/commit/fc74d5f669fa103c0854357e47f5ef6d775235b4))
- sync bilingual manuals with latest features [缺中文] ([`8b17bf1`](https://gitee.com/jermaine/yate/commit/8b17bf1ca75add80441eecf7c38fc43f1984a3ee))
- link bilingual manual prominently at the top [缺中文] ([`b3b4e81`](https://gitee.com/jermaine/yate/commit/b3b4e81222b1fecefc1d8dca9af08cb5d6bff874))
- add extensions, themes and LSP configuration guides [缺中文] ([`bf46092`](https://gitee.com/jermaine/yate/commit/bf46092b6e99cbdc6161d4ee13ebc72c5d284a08))
- cover integrated terminal in help, welcome page and docs [缺中文] ([`475a650`](https://gitee.com/jermaine/yate/commit/475a650f9b2ec52ef153949c17d8dd4c4aaf9a62))

### 测试

- 补充变更日志门禁、运行时文档屏与 CLI 参数测试 ([`1060811`](https://gitee.com/jermaine/yate/commit/10608119b9d848a2025f3a870cedf7455a0e68b9))
- harden rc server parsing and cover declarative LSP paths [缺中文] ([`3ad2a7e`](https://gitee.com/jermaine/yate/commit/3ad2a7ee9751ae3e6a588d75d737aea67649c9a3))

### 构建与工程

- 为发布提交补充中文翻译 ([`6fa7663`](https://gitee.com/jermaine/yate/commit/6fa7663f9ea781576e1178778c7182f52f60bc7b))
- CI 拉取完整历史以支持变更日志门禁 ([`a1d81d6`](https://gitee.com/jermaine/yate/commit/a1d81d6117f51634654361a6993d29921b8c0c1b))
- 打包时刷新随包变更日志 ([`b0ca383`](https://gitee.com/jermaine/yate/commit/b0ca3838870208978a676daa94b1e9eec5357835))
- 为两条 CI 流水线添加变更日志新鲜度门禁 ([`1998c82`](https://gitee.com/jermaine/yate/commit/1998c82fbb4aa17972a60310bdfaa002d786925a))
- 项目版本改为从 yate/__init__.py 动态读取 ([`7b5dd93`](https://gitee.com/jermaine/yate/commit/7b5dd93b01d8fa9dc2bb5fe77e946e57f7e2860a))
- ship docs/ in the wheel so manual links resolve after install [缺中文] ([`7b62b6c`](https://gitee.com/jermaine/yate/commit/7b62b6c1c5cc0520fdbbd257b161810ea3e30813))
- drop the old unrenamed manual.md [缺中文] ([`17a0259`](https://gitee.com/jermaine/yate/commit/17a0259c5ffade09f8937e0ec9892a27eaadd82a))

### 其他变更

- 新增 yate --diag 诊断命令并扩展 --version 输出 ([`b6d1071`](https://gitee.com/jermaine/yate/commit/b6d10711004e5d6303638151c838bbf552265c3f))
- 新增 vim 风格窗格分割与资源管理器过滤 ([`ecadd41`](https://gitee.com/jermaine/yate/commit/ecadd4162c2df393492fe316e6535d8e332355ac))
- 随包扩展遮蔽时告警；包内剔除字节码；修复 Windows 8.3 配置路径 ([`db93b52`](https://gitee.com/jermaine/yate/commit/db93b52af796ff953f9124a8314e881e39c35480))
- 新增 GitHub Actions CI（Linux/Windows 矩阵） ([`949ed01`](https://gitee.com/jermaine/yate/commit/949ed01791e3cca2dbc1955158c8fb52978d5a32))
- 新增 Gitee Go 流水线运行全量单元测试 ([`a2e3195`](https://gitee.com/jermaine/yate/commit/a2e3195f96b3413758dbae342618ae531e6b9d35))
- Move PyInstaller specs into pack/ and anchor paths to SPECPATH [缺中文] ([`f355a44`](https://gitee.com/jermaine/yate/commit/f355a44a6e1b7213570ef3b29a31671b5bae4662))
- Add cross-platform PyInstaller build scripts under pack/ [缺中文] ([`28a2a41`](https://gitee.com/jermaine/yate/commit/28a2a41bde57715af650a9d235768d0f42810e88))
- Clear stale status message on overlay commands and confirm silent ones [缺中文] ([`93845b3`](https://gitee.com/jermaine/yate/commit/93845b353cdc1477b6c406aad7e9383f002fe526))
- Add onefile PyInstaller spec producing a standalone dist/yate.exe [缺中文] ([`7cdd551`](https://gitee.com/jermaine/yate/commit/7cdd55149eec892586fd7dcb7c819edae0dba236))
- Sync READMEs with current implementation [缺中文] ([`d2c49df`](https://gitee.com/jermaine/yate/commit/d2c49dfdb8850ed0faa21484e37c0878f410483a))
- Make English the default README (README.md), Chinese becomes README.zh.md [缺中文] ([`3835554`](https://gitee.com/jermaine/yate/commit/3835554022e4e2b6ff0f042d3685a0f6e996620a))
- Bundle docs and extensions inside yate; add PyInstaller packaging [缺中文] ([`783f491`](https://gitee.com/jermaine/yate/commit/783f49116ab521840474feaa94113f48afa4be87))
- Initial commit [缺中文] ([`f690bf7`](https://gitee.com/jermaine/yate/commit/f690bf7d5f8be18de9b74b4006fcd50d18fda0d7))
- Initial commit: yate terminal editor [缺中文] ([`ef1d964`](https://gitee.com/jermaine/yate/commit/ef1d964ecc5366cd6bf4c3da943e2371608e748a))
