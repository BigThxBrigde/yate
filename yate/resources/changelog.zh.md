# 变更日志

> 由 git 历史自动生成于 2026-09-23 · yate 0.2.4

## [未发布] · [compare](https://gitee.com/jermaine/yate/compare/v0.2.4...HEAD)

### 新功能

- 扩展加载增加工作区信任门禁 ([`a89a720`](https://gitee.com/jermaine/yate/commit/a89a720737dc808ddd2975a98855b6ae76a158dc))
  - 新增 :trust 命令与 ~/.yate/trusted_workspaces 信任库；未受信工作区的 ./extensions 不再自动加载
- 编辑核心记住垂直移动的目标列 ([`b0d154d`](https://gitee.com/jermaine/yate/commit/b0d154d8972ad2e44967d3956a5e61f63d058581))
  - 跨短行下移后不再永久丢失原列，与 vim / VS Code 行为一致
- 为可执行文件生成基于 logo 的图标 ([`54cf062`](https://gitee.com/jermaine/yate/commit/54cf062e6cf451198ed03a63e30186be7f289752))
  - 新增 tools.pack icon 子命令生成 pack/yate.ico，Windows 构建启用图标，Linux 保持无图标
- 新增可选的运行时 trace 日志 ([`8b66b89`](https://gitee.com/jermaine/yate/commit/8b66b896d2475bde741893dbdc7a8b62154d5e2f))
  - 默认关闭，经 YATE_TRACE/YATE_TRACE_LEVEL 或 yaterc 选项开启，写入 ~/.yate/data/logs
- 冒烟脚本新增压力场景与别名覆盖（S 组） ([`4d357cc`](https://gitee.com/jermaine/yate/commit/4d357ccb78c60434848d30c6d3183834c43d36b0))
  - 含按键模糊、多标签、大文件等场景，命令覆盖率升至 60%
- 冒烟脚本新增历史缺陷回归守卫（R 组） ([`25fdbd8`](https://gitee.com/jermaine/yate/commit/25fdbd8066c0cc3613fa3f65c2b12c547f1a0b6a))
- 冒烟脚本新增集成场景（H 组） ([`f25aaba`](https://gitee.com/jermaine/yate/commit/f25aabaf3851fbc70d781b8e93259eb23b5bee7c))
- 冒烟脚本新增窗格、资源管理器与视图场景（E/F/G 组） ([`5c22c8d`](https://gitee.com/jermaine/yate/commit/5c22c8dffa8062f0d12f3c1b8c506d9a441ca1e4))
- 冒烟脚本新增搜索与文件/标签场景（C/D 组） ([`0d4a2fe`](https://gitee.com/jermaine/yate/commit/0d4a2fedf03a2342563d05c417690735e6c54153))
- 冒烟脚本新增编辑与选择场景（A/B 组） ([`544e56d`](https://gitee.com/jermaine/yate/commit/544e56ddfe2a7f5ad334d6d960191988e54d40da))
- 重构冒烟测试框架：标记化场景与 Rich 报告 ([`f1787bc`](https://gitee.com/jermaine/yate/commit/f1787bc88052f03a646da88f634386a8824130a7))
- 新增 yate UI 冒烟测试工具（run/snapshot/compare） ([`47dac93`](https://gitee.com/jermaine/yate/commit/47dac9311ad21b91a2aa1552716d19e1529dd3fc))

### 问题修复

- 修复补全弹窗吞掉按键：其余键正常分发，可继续输入过滤候选 ([`bbeb5f6`](https://gitee.com/jermaine/yate/commit/bbeb5f6375142e1a64febf6049a4db33812c5efa))
  - 弹窗打开时仅消费 tab/enter/up/down/esc，字符照常写入缓冲区并按新前缀重新查询；Ctrl+S / Ctrl+Z 等全局快捷键恢复；新增测试与冒烟守卫（原场景此前恒真）
- 修复冒烟命令总集快照时机 ([`d6765c4`](https://gitee.com/jermaine/yate/commit/d6765c419394afeac842667d489c49973b699f6a))
- 修复键入路径分隔符后目录补全为空 ([`c55f71e`](https://gitee.com/jermaine/yate/commit/c55f71e3793e80919305e3d453e6bde6b75de480))
  - 此前键入 / 会清空补全弹窗，需再输入子项首字母才恢复
- 修复字体安装跳过无法删除的注册表残留 ([`7d0e698`](https://gitee.com/jermaine/yate/commit/7d0e698276ebeb85c15bf5eb701aa68defa123a5))
- 修复 replace_all 后光标越界并在冒烟中覆盖 ([`ea3a323`](https://gitee.com/jermaine/yate/commit/ea3a323c2ceca5bd5e2b603bc03e5e564ade0b95))
- 修复撤销/重做后脏标记不准确 ([`5190225`](https://gitee.com/jermaine/yate/commit/5190225a9173dfa4ccf86b617364b9f35b39e902))
  - 为合并编辑引入权重计数，必要时回退到精确行比较
- 保存改为原子写并限制撤销栈内存 ([`05106d5`](https://gitee.com/jermaine/yate/commit/05106d56d7107670aae1a8bb3ec240d21a043e74))
  - 临时文件加 os.replace 落盘，撤销栈上限 1000 步，并跳过符号链接目录防止死循环
- 修复 PTY 启动失败时退出 Future 未完成 ([`9828b24`](https://gitee.com/jermaine/yate/commit/9828b24ba34715602d124fec7ca8335dfb8b2149))
- 修复日志卸载钩子：恢复 sys.excepthook 并去重 atexit ([`1c0a086`](https://gitee.com/jermaine/yate/commit/1c0a086b11d1e010b37069d2db8ab8130716374f))
- 修复懒加载日志流的 None 判断依赖类型存根问题 ([`4ded5ac`](https://gitee.com/jermaine/yate/commit/4ded5ac9d536e3aaf1be392a6538ddf5eb401d3f))
- 修复 trace 日志级别解析并改为惰性创建日志文件 ([`3a6f9f9`](https://gitee.com/jermaine/yate/commit/3a6f9f923a6ea456b93a26f5069284025265cebf))
  - falsy 级别不再被改写为 DEBUG；YATE_TRACE=1 遇提前退出命令时不再残留空日志
- 修复冒烟测试在文档路径为空时的崩溃 ([`06b1f37`](https://gitee.com/jermaine/yate/commit/06b1f37472d9557be9f225fd9595c8055eb65e56))
- 修复冒烟测试发现的三个编辑器状态缺陷 ([`4df4e2b`](https://gitee.com/jermaine/yate/commit/4df4e2be8befc29e950c5f6f2d3b81f077036560))
  - 涉及缩进后光标越界、保存失败清空文件、无输出命令卡死命令行
- vim 键位绑定 ctrl+/ 切换，冒烟脚本改用 F5 进命令行 ([`8af7457`](https://gitee.com/jermaine/yate/commit/8af745764fdb6bdae55c72478e317e1b586dc5cc))
  - 此前 ctrl+/ 被普通模式吞掉，vsc 与 vim 只能单向切换
- 修复删除文件夹关闭标签时未通知 LSP 的问题 ([`649f113`](https://gitee.com/jermaine/yate/commit/649f113e632a107236bd3499ba15c95c06c3c7d1))
- LSP 通知改为向 worker 传递协程函数而非已构建协程 ([`c020bc6`](https://gitee.com/jermaine/yate/commit/c020bc62a29a40172b29300f378e951edf9aafe5))
- 修复保存失败时 :wq 仍强制退出 ([`68c797d`](https://gitee.com/jermaine/yate/commit/68c797d854feed6aa15684f3c2ab8768c077ef65))
  - 保存失败或未命名缓冲区现保留编辑并提示，避免丢失未保存内容
- 打包脚本改用 .NET SHA256 接口计算文件哈希 ([`0d06e94`](https://gitee.com/jermaine/yate/commit/0d06e947ec7e94324a978584da388fe02e21a97a))
- vim 键位支持 F1 到 F12 ([`91d40d8`](https://gitee.com/jermaine/yate/commit/91d40d8ed00e44f97a1ee13842d1a7e3162d6934))

### 性能优化

- 冒烟测试批量注入按键并降低轮询间隔以提速 ([`9f94d8e`](https://gitee.com/jermaine/yate/commit/9f94d8e280b625882fd8dc769e6ceaaf785c8e11))
  - 移除每键约 20ms 的空转睡眠，多个输入场景提速数倍

### 重构

- 窗格树模型下沉至 session.py（Plan G） ([`2ee2586`](https://gitee.com/jermaine/yate/commit/2ee258656b04517c0a94030c990b27f6f13b1e9a))
  - 删除 editor_view/pane_types.py，Leaf/Split/ViewState 与树操作并入 L1 session，EditorSession 仍与窗格无关
- 拆分 refresh_ui 为多个子方法并更新过期文档 ([`f3df035`](https://gitee.com/jermaine/yate/commit/f3df0358309173d961e7a35575118b44e90dbdef))
- 架构分层重构：外壳瘦身并移除 app_features 与窄接口，新增 Editor 调度层与 EditorSession 会话层 ([`9fa5ac8`](https://gitee.com/jermaine/yate/commit/9fa5ac84b844958bd89bcc6b039dc1ed30a5897e))
  - 用户可见变化：扩展里的 api.app 由 YateApp 变为 ExtensionContext（可用字段见扩展文档）；api.keymaps 由 dict 变为 KeymapSet。
- 以窄接口模块协议替换 AppProtocol ([`738204e`](https://gitee.com/jermaine/yate/commit/738204e4e36f592e33aa1b775f21ec45634f8bde))
  - 外壳不再对外暴露宽 AppProtocol，改按模块暴露窄协议
- 日志重构：移除 crash/tracing 外壳，直接导入单例 ([`78a2696`](https://gitee.com/jermaine/yate/commit/78a26968c091fde3d7438490de0130006e8eb351))
- 将崩溃诊断与追踪日志统一到 yate/logs.py ([`4cdf4da`](https://gitee.com/jermaine/yate/commit/4cdf4da449b36dfe42eab2939ea681a44abc4014))

### 文档

- 补齐全部缺失的中文翻译并刷新双语变更日志 ([`32e5649`](https://gitee.com/jermaine/yate/commit/32e56490166bece249be93982769f7c31833521c))
  - zh_overrides.json 由 42 条扩至 202 条，重新生成后有 0 条缺译
- 注释与 docstring 全部改为英文 ([`844cd0a`](https://gitee.com/jermaine/yate/commit/844cd0acefd38997968bc53038914bc5f6ffcba8))
- 文档更正退出动作结论并登记冒烟调查问题 ([`c1f83fe`](https://gitee.com/jermaine/yate/commit/c1f83fec05efbc55a125db10f2f0b36c4312a71c))
- 文档记录场景覆盖率轮次与前后对比 ([`4b0695a`](https://gitee.com/jermaine/yate/commit/4b0695ad4afcf81ff3e41773c5b741ddc40162f3))
  - 命令/动作覆盖由 63%/78% 提升至 100%/100%，场景 65→86、断言 688→889
- 新增窗格模型下沉至 L1 session 的计划 ([`277abf9`](https://gitee.com/jermaine/yate/commit/277abf904f954e0155636076c18ae055f78cb3e5))
- 记录第二轮覆盖率结果与冒烟覆盖修复 ([`c2be8dd`](https://gitee.com/jermaine/yate/commit/c2be8dd809944f673dae137ba587a52dd8bee1e0))
- 规则新增子代理静默丢失的防护条款 ([`a1c35b2`](https://gitee.com/jermaine/yate/commit/a1c35b26a86591d14cdbcce96535828a3918d47a))
- 开启第二轮覆盖率计划（PTY、字体、弹窗） ([`802467d`](https://gitee.com/jermaine/yate/commit/802467d6fd94ab3910310b199bc6d9bf8a1e3abc))
- 记录覆盖率实现与标定过程 ([`fd251e1`](https://gitee.com/jermaine/yate/commit/fd251e19a568dc8dac787aef9ed5b2e4a2371a33))
- 规则要求子代理并行执行且上限五个 ([`942821a`](https://gitee.com/jermaine/yate/commit/942821ac6b7d85eb9cbf992c00de22bcb60ff55a))
- 新增代码覆盖率与测试扩充计划 ([`1c0a7e0`](https://gitee.com/jermaine/yate/commit/1c0a7e0bac78a4a16ec09a90fd44d8718b3e4b1e))
- 重构审查记录结构并拆分修复计划 ([`f33c54a`](https://gitee.com/jermaine/yate/commit/f33c54ac498393521df7bf066f7498f500446f25))
- 新增代码审查修复计划记录 ([`a270bd3`](https://gitee.com/jermaine/yate/commit/a270bd3aea7eab1be622a66bc3d17d0564bc18e1))
- 文档收尾 Plan E/F：计划、规则、用户文档与变更日志 ([`6b43972`](https://gitee.com/jermaine/yate/commit/6b439727fb6f2eb664609a8f6681338cd59032a7))
- 对照代码审计分层计划并收紧守护测试 ([`d1bfdbf`](https://gitee.com/jermaine/yate/commit/d1bfdbfd2b8c87ba91a4fc5aa06124ec90765d58))
- 审计计划文档与当前代码的一致性 ([`4cb06a3`](https://gitee.com/jermaine/yate/commit/4cb06a361fabf691ed3d9d247cda7c51102c64af))
- 新增架构边界规则并对齐 TYPE_CHECKING 指南 ([`21db510`](https://gitee.com/jermaine/yate/commit/21db5101d244583217a8260e00cf502bdff86c9c))
- 新增拆分并移除 AppProtocol 的草案计划 ([`e8f8d05`](https://gitee.com/jermaine/yate/commit/e8f8d052489176928584cb4f05feceade41bd3a0))
- 按单模块设计重写崩溃与追踪计划 ([`57bcdd6`](https://gitee.com/jermaine/yate/commit/57bcdd609986ee6de6339fe782ca8b88f86f9a6d))
- 重写崩溃与追踪计划以匹配实现 ([`d4919c7`](https://gitee.com/jermaine/yate/commit/d4919c75e4a6dedb8e07463ee4a4acb311cc69ac))
- 更新日志重构计划 ([`35830eb`](https://gitee.com/jermaine/yate/commit/35830eb1c479e6bfc50b432d7d9c401fa0a65f05))
- 新增日志重构计划 ([`35fa904`](https://gitee.com/jermaine/yate/commit/35fa904157d2bdd70f9be9c86a785dcf65eb712e))
- 新增 Python 代码风格规范 ([`6e9f013`](https://gitee.com/jermaine/yate/commit/6e9f013dfe6d5993079b2985cc5aa1152b75b061))
- README 补充可执行文件图标章节并同步中文版 ([`f3e8c89`](https://gitee.com/jermaine/yate/commit/f3e8c89a1ee109aef6019bef93d88779b54583f5))
  - 中文版删除重复拼接内容并镜像英文更新，测试数修正为 612
- 文档新增运行时 trace 日志实现方案 ([`91d1345`](https://gitee.com/jermaine/yate/commit/91d134592013a9f12099a2ccf96386e1d4686a61))
- 文档同步 --help 输出与 CLI 选项说明 ([`ac41c84`](https://gitee.com/jermaine/yate/commit/ac41c84f925ac25f37526a6c4f35fc9b51aed27d))
- README 补充冒烟测试用法 ([`9e6b487`](https://gitee.com/jermaine/yate/commit/9e6b48719f3ad8b21344afc8fa8859ea521004cd))
- 文档记录重构后的冒烟测试框架并提交基线 ([`925ea06`](https://gitee.com/jermaine/yate/commit/925ea0630a39af7e6093d08fb061b2519ec8255e))
- 文档新增冒烟测试框架修复、扩展与改造方案 ([`20227ad`](https://gitee.com/jermaine/yate/commit/20227ada961c3751482bd9c91e947227e6ea507e))
- 更新问题跟踪并新增 LSP 修复方案 ([`61bc850`](https://gitee.com/jermaine/yate/commit/61bc8500525ad8b8bfb753182f217bafadf2ac5c))
- 文档新增补全过期校验修复方案 ([`7ddaced`](https://gitee.com/jermaine/yate/commit/7ddaced073a4a9d9102fc80f38651a9729993464))
- 整理并修正 git 提交规范文档 ([`f677c73`](https://gitee.com/jermaine/yate/commit/f677c734ab2fa79e0cf0529badfb0db1789f6468))
- 更新问题跟踪文档，整理全量代码审查问题 ([`807c199`](https://gitee.com/jermaine/yate/commit/807c199c95981ed5eac850025558d42fbf1e00e8))

### 测试

- 冒烟测试覆盖全部已注册命令与动作 ([`0984361`](https://gitee.com/jermaine/yate/commit/09843611fdf12a69273e561750db7a75109eb65d))
  - 新增 19 个场景（65→86），命令与动作覆盖达到 43/43、65/65，未改动产品代码
- 补全测试覆盖弹窗几何与缓冲区补全源 ([`f01b713`](https://gitee.com/jermaine/yate/commit/f01b713dd490a2303decc730e21784da1a3dbaef))
- 字体测试覆盖注册表扫描、检测、安装与设置改写 ([`a6dcbef`](https://gitee.com/jermaine/yate/commit/a6dcbef8f2822d45b59cc0d52e975eedfbc3300b))
- PTY 测试覆盖各平台后端与门面失败路径 ([`64e2dd4`](https://gitee.com/jermaine/yate/commit/64e2dd48e51e9331f287770767d222c49f94326a))
- 测试与冒烟场景迁移至编辑器层 ([`61f988d`](https://gitee.com/jermaine/yate/commit/61f988d68fde73daa89cd37e7f62690026b50cd4))

### 构建与工程

- 忽略本地 CodeBuddy 工作区数据 ([`b2658a6`](https://gitee.com/jermaine/yate/commit/b2658a607914ed04dc9bdae52f3e39cb248dcf87))
- 无头测试覆盖 vim 键位 ([`0096123`](https://gitee.com/jermaine/yate/commit/009612391a2f85ca36e013ee8646949c31e0b839))
- 无头测试覆盖终端模拟器 ([`fdbfa10`](https://gitee.com/jermaine/yate/commit/fdbfa10566eee8086d3a27c03ee48c65fb35417c))
- 测试覆盖工作区列举、变更与嗅探路径 ([`97b6205`](https://gitee.com/jermaine/yate/commit/97b6205509a8f303583f293bf9d609e153dca0c8))
- 测试覆盖诊断报告边界情况 ([`e449dd1`](https://gitee.com/jermaine/yate/commit/e449dd1cb72effdf7c9b04623a75b6b052b4a018))
- 测试覆盖会话、注册表、外壳与补全模块 ([`6bbe908`](https://gitee.com/jermaine/yate/commit/6bbe9082248c5c2533c8f1e629171b384e7ec951))
- 新增行/分支覆盖率门禁并扩充核心测试 ([`1e15a16`](https://gitee.com/jermaine/yate/commit/1e15a1632f187de51e97a8d026960fd497e2c5a9))
  - CI 以 --cov-branch --cov-fail-under=75 运行；buffer/search/document 覆盖率大幅提升
- 测试显式引用主题清理 fixture 以消除告警 ([`719e73a`](https://gitee.com/jermaine/yate/commit/719e73a84756b87234cc9cd26d3bbb456195279d))
- 修复追踪测试在 pyright 严格模式下的告警 ([`033c7e9`](https://gitee.com/jermaine/yate/commit/033c7e9104c26fbe63cbdaa7f4a94aec0dc22a70))
- 忽略冒烟测试生成的临时 JSON 报告 ([`8937dc3`](https://gitee.com/jermaine/yate/commit/8937dc3d358beacdc638e42f40580ad26783108a))
- 冒烟测试基线目录迁入 smoke_test 包内 ([`adfbc9c`](https://gitee.com/jermaine/yate/commit/adfbc9ce6265b7851c0b914f609df1dd8f817c35))
- 新增 vscode 工作区配置并更新 gitignore ([`c33258b`](https://gitee.com/jermaine/yate/commit/c33258b80b36213f747b4b4051a15189e8e3356e))
- 新增 git 提交规范文件并修复 :wq 命令 ([`b33706c`](https://gitee.com/jermaine/yate/commit/b33706c21979babaa5afe12edc8be10ddd62d29d))
- 更新 yaterc_pywright 方案文档 ([`0971a72`](https://gitee.com/jermaine/yate/commit/0971a726695f8e586c4bc2acfbe408e8a25a7efd))
- 更新开发方案文档 ([`5ac2bb4`](https://gitee.com/jermaine/yate/commit/5ac2bb4ceb1845e6a97f140f4e48470c84cc614f))
- 更新开发方案文档 ([`ab75198`](https://gitee.com/jermaine/yate/commit/ab75198382e8dbd8a0e00733dbfce9df969f0f18))
- 更新变更日志 ([`03c9dee`](https://gitee.com/jermaine/yate/commit/03c9dee7d7ef81f05bc3440e2b85a1045a933ed5))
- 更新变更日志 ([`798df3a`](https://gitee.com/jermaine/yate/commit/798df3a6a16ab03f370b5f2a707f6e08c54d2c74))
- 更新技能文档 ([`54de33c`](https://gitee.com/jermaine/yate/commit/54de33c699bd11c35579472974d9d5cffe8fccc8))
- 新增方案文档 ([`53a7e09`](https://gitee.com/jermaine/yate/commit/53a7e099bf53ff8fa0be43bd2b5bba258f84709b))
- 移除变更日志中的多余换行 ([`cf67891`](https://gitee.com/jermaine/yate/commit/cf67891a2a9f171faac752d0fe5c53528b9ae50b))
- 修正变更日志的主仓库地址 ([`90b71cc`](https://gitee.com/jermaine/yate/commit/90b71cc90378dee62d8c82da6f72a73797c2345e))

### 其他变更

- 修复补全触发与校验逻辑的若干边界情况 ([`cc4b1f6`](https://gitee.com/jermaine/yate/commit/cc4b1f6ef164952d0dccaf60ab8d5c203539cd72))
- 重构窗格分割模块以解除类型循环依赖 ([`1325f71`](https://gitee.com/jermaine/yate/commit/1325f71edbe70046ac53384d3e988f6660a9ea4c))
- 改进退出处理并补充错误覆盖 ([`3b4319a`](https://gitee.com/jermaine/yate/commit/3b4319a208a2c479de0c67d4d3f136743ac1f885))

## [0.2.4] - 2026-09-15 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.3...v0.2.4)

### 新功能

- 为所有配色方案补齐提示符配色 ([`8ae5da6`](https://gitee.com/jermaine/yate/commit/8ae5da6d5df1277b97dc56195abcea1d4107855a))

### 问题修复

- 修复 test_app_textual 的竞态 ([`6bb2179`](https://gitee.com/jermaine/yate/commit/6bb21799d9984e30a56f4fb24604ba1da9c5ea53))
- 变更日志排除发布文档提交以稳定门禁 ([`677f867`](https://gitee.com/jermaine/yate/commit/677f867fad1319041e5c41e4a618d42709771114))

### 构建与工程

- 更新遮罩层主题一致性方案 ([`e3e5a37`](https://gitee.com/jermaine/yate/commit/e3e5a376f7acef8fa8e5be8c9d2b1ad136c0eada))
- AI 文档改为英文并同步更新 ([`e065440`](https://gitee.com/jermaine/yate/commit/e065440e92968a594e682a5cb3c3ff6145dcc33e))
- 新增 AI 协作文档 ([`f056703`](https://gitee.com/jermaine/yate/commit/f05670327ed749bebca277f3cb9bc35cbe42defe))
- 忽略 pyenv 本地配置 .python-version ([`adae5f7`](https://gitee.com/jermaine/yate/commit/adae5f71f65f33894dfc276674c5eab8bbc8d913))

## [0.2.3] - 2026-09-15 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.2...v0.2.3)

### 问题修复

- 修复发布工具并补全源码版本号 ([`5ff9d8b`](https://gitee.com/jermaine/yate/commit/5ff9d8b8580cf5e99c433aee1413896f9cff04f7))

### 文档

- 在未发布段记录 pytest 迁移 ([`449eb30`](https://gitee.com/jermaine/yate/commit/449eb307d769586431855b488aec0dbc97e45abb))

### 测试

- 测试套件从 unittest 迁移到 pytest 并隔离 HOME ([`14e6dd3`](https://gitee.com/jermaine/yate/commit/14e6dd372dbc3ecaadc52c2080a403eb5555599f))

## [0.2.2] - 2026-09-14 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.1...v0.2.2)

### 新功能

- 新增发布工具并简化发布流程 ([`4fec66d`](https://gitee.com/jermaine/yate/commit/4fec66d427ef3744ff91d1b6e101799eac915c60))

### 问题修复

- 补全前冲刷待发的 didChange，优先用解释器旁的 pyright ([`fa1ae55`](https://gitee.com/jermaine/yate/commit/fa1ae55aafd5b02fafe502560bf1bdc53f21e0cb))
  - 补全弹窗上限由 50 提到 250，避免标准库模块被截断
- 修复发布工具被忽略的问题 ([`1758fff`](https://gitee.com/jermaine/yate/commit/1758fffb6543479a7c153ab9d374820641ab8147))
- 语法高亮防抖并复用未失效的 token ([`082bc7d`](https://gitee.com/jermaine/yate/commit/082bc7d3c2824e2314b06b70ff97e5a310af0219))
  - 编辑时沿用上一帧 token 缓存着色，文档或文件类型切换仍立即失效
- 修复 test_vsplit_with_file_and_only 并升级版本 ([`ceba77f`](https://gitee.com/jermaine/yate/commit/ceba77ff8e92646899e4a9c2e65af5e0359d5076))

### 构建与工程

- 更新 CHANGELOG ([`641412c`](https://gitee.com/jermaine/yate/commit/641412c7ae4701e7462b44628437382d74b0895e))
- 更新 README.zh.md ([`8566fac`](https://gitee.com/jermaine/yate/commit/8566fac589c6524486f3b4c3907f40fcd10ce851))

## [0.2.1] - 2026-09-14 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.0...v0.2.1)

### 新功能

- 打包新增 --dist 产物暂存并强制使用 .venv 解释器 ([`483b667`](https://gitee.com/jermaine/yate/commit/483b6679d93cc0773390887dfc38f3bc9716a620))
  - 同名版本子目录被替换，写出 SHA256SUMS.txt，并以 --version 冒烟测试把关；缺少 .venv 直接报错退出
- 修复失败的单元测试 ([`5b03805`](https://gitee.com/jermaine/yate/commit/5b0380563819be1434e38f3c1dd835ca52a98695))

### 文档

- 刷新随包变更日志资源 ([`107b17c`](https://gitee.com/jermaine/yate/commit/107b17c94f912002cf46802c48281930985834a0))

## [0.2.0] - 2026-09-14 · [compare](https://gitee.com/jermaine/yate/compare/v0.1.1...v0.2.0)

### 新功能

- 新增 --setup-defaults/--cleanup-defaults 一键初始化与清理用户配置目录 ([`04ec16e`](https://gitee.com/jermaine/yate/commit/04ec16ea59bcc748b39ca78d1aaf3b1de9675c73))
  - 模板以 .example 原后缀发放、改名 .py 才激活；cleanup 需确认且默认保留 data/；新增 crash.uninstall 解决 Windows 句柄占用

### 文档

- 文档同步一键初始化/清理命令（手册、主题与 yaterc 指南、README） ([`738c2f1`](https://gitee.com/jermaine/yate/commit/738c2f1bb22b0b14aaa62a6c683a0793a93ca459))

### 测试

- 补充用户配置初始化/清理服务层、CLI 参数透传与崩溃句柄释放测试 ([`6e77ebe`](https://gitee.com/jermaine/yate/commit/6e77ebed0050caf573d644218a070d7b0d7f3a8a))

## [0.1.1] - 2026-09-14 · [compare](https://gitee.com/jermaine/yate/compare/v0.1.0...v0.1.1)

### 新功能

- 随包附带 Dracula 与 Ayu 主题模板，复制为 *.py 后即可启用 ([`28d74c5`](https://gitee.com/jermaine/yate/commit/28d74c57076ee941bd400f358eeb4bec3ea9ac52))
- 新增 One Dark/Light 与 Gruvbox dark/light 四套内置主题 ([`a4d880b`](https://gitee.com/jermaine/yate/commit/a4d880bf2534d3e8970d2757a0631e9718148840))
  - 内置主题由 4 套扩至 8 套，默认仍为 mocha，可用 :theme 即时切换

### 问题修复

- stop() 等待进行中的连接，确保已启动的 LSP 进程退出 ([`7c69c6b`](https://gitee.com/jermaine/yate/commit/7c69c6bbece7a13691b76ab4786f1e7543a13c02))

### 文档

- 文档同步八套内置主题与模板安装方式（README、手册、主题指南） ([`26ba949`](https://gitee.com/jermaine/yate/commit/26ba949ed4a4bce041533e2308803e52d19b3fc5))
- 把变更日志维护附录从手册移到 README ([`33190c5`](https://gitee.com/jermaine/yate/commit/33190c5a10e073ecd5c6cccefa7ecc083d859828))

### 测试

- 补充内置色板与主题模板加载测试，修复旧测试注册表泄漏与版本号硬编码 ([`a4aaa68`](https://gitee.com/jermaine/yate/commit/a4aaa68c349a4cb5c6f7bb09d9549ed26d402a1d))

### 构建与工程

- CI 固定 Gitee 为 origin，让变更日志门禁在 GitHub 通过 ([`76518e0`](https://gitee.com/jermaine/yate/commit/76518e04a14c895507a74a854e93a9fbaa7a49ef))
  - checkout 会把 origin 指向 GitHub 镜像，导致已发布段被误判过期
- 冻结构建随包捆绑 tree-sitter 后端与 python/bash 语法 ([`74202ac`](https://gitee.com/jermaine/yate/commit/74202accea55e7c6339eb060e3e11d4b29b22dbd))
  - spec 显式收集子模块、原生绑定与 *.scm 高亮查询

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
- 新增 yaterc language_servers 声明式选项并自动激活 ([`e1615f0`](https://gitee.com/jermaine/yate/commit/e1615f088061cd435659b0d429ff55690ec31cea))
- 命令行裸数字跳转行号，新增 Ctrl+G 跳转提示 ([`4ccd904`](https://gitee.com/jermaine/yate/commit/4ccd9041726904e0629fb905067fd0649b7c3fe1))
- 扩展可注册自定义语法高亮，随包附带 C# 示例 ([`db82bce`](https://gitee.com/jermaine/yate/commit/db82bcea306058ac1919a42f054f971e8301129c))
- 新增 :set filetype 手动切换语法与文件类型 ([`8e9337a`](https://gitee.com/jermaine/yate/commit/8e9337a0c8f49691dcbbe3023f08e745c9a12f7b))
- vscode 键位下 F5 打开 ex 命令行 ([`669f017`](https://gitee.com/jermaine/yate/commit/669f017b6c32a5731db8679fa4c31f78616845b9))
- 基于 buffer 的自动补全与 bash 式 Tab 补全 ([`bcd0426`](https://gitee.com/jermaine/yate/commit/bcd04266064ae148ab4d69e96aad5e14933cd80b))
- 新增 --theme 参数，修复 --theme-dir 的 ~ 展开 ([`5e69220`](https://gitee.com/jermaine/yate/commit/5e692204956e1b809f94a99bac08732c7661ad01))
- 手册支持内置搜索（/ 或 Ctrl+F） ([`f002de4`](https://gitee.com/jermaine/yate/commit/f002de48dbd612275b04711ad2db5c11f82cc8a6))
- 命令面板列出全部命令与动作，可按全名搜索 ([`eb4016e`](https://gitee.com/jermaine/yate/commit/eb4016efc261c4391e7cc553de4ca8a3c4b26a77))
- 用 theme_dirs 与 --theme-dir 支持自定义主题目录 ([`53af6de`](https://gitee.com/jermaine/yate/commit/53af6defaff10e126c31c805904d0e2da40a1d3e))
  - 从外部 *.py 加载主题，优先级为 内置 < 默认目录 < yaterc < --theme-dir
- 集成终端面板（PTY 驱动），快捷键开关 ([`ee7cd53`](https://gitee.com/jermaine/yate/commit/ee7cd5323555bb7309a2fc41405911863e4cacb3))
- LSP 支持：自动补全与诊断 ([`ad28ef5`](https://gitee.com/jermaine/yate/commit/ad28ef5fb3963d6798833d4ae53d577a00c4617c))
- 键位：资源管理器与编辑器间的窗口切换 ([`8cd80b2`](https://gitee.com/jermaine/yate/commit/8cd80b26cf389d6a713fd361c079f59d138e2748))
- 双语用户手册（英/中），打开时套用主题，修复表格布局 ([`a819973`](https://gitee.com/jermaine/yate/commit/a819973a7d943be31df221ae10f549f6d3f1654b))
- 内置只读用户手册查看器（F8 / :manual） ([`88d6b52`](https://gitee.com/jermaine/yate/commit/88d6b52e1ddeb789c5eb7e4776ed3d5d4e32fd1a))
- 欢迎页横幅改用 ANSI Shadow figlet 风格 ([`2cf85a1`](https://gitee.com/jermaine/yate/commit/2cf85a113005dc140697ffe1d1eaf5176d2fcf6a))
- 命令面板改绑 alt+shift+p ([`ba6d7a6`](https://gitee.com/jermaine/yate/commit/ba6d7a6a3852132fbcc5f7d498eb896de2975c88))
- 随包捆绑 JetBrains Mono Nerd Font；修复 Windows Terminal 配置覆盖 ([`d2ce815`](https://gitee.com/jermaine/yate/commit/d2ce8158eba4619836b41ec067b810a752842556))

### 问题修复

- 防护 tree-sitter 0.26 在 Windows 上的堆内存损坏 ([`85cb9ad`](https://gitee.com/jermaine/yate/commit/85cb9ad740f2a218f16c5e5c50e67a6d3612d144))
- 修复 Windows CI 竞态：停止期间的 LSP 子进程与 8.3 短路径 ([`3f4c4db`](https://gitee.com/jermaine/yate/commit/3f4c4dbc43144b89b6fcedf964bee7ec66758543))
- LSP didChange 同步重试、扩展卸载钩子与打包规格跟踪 ([`6cf4fea`](https://gitee.com/jermaine/yate/commit/6cf4fead2daea53083300332eb96751e2bc5c4f7))
- 修复 :q 始终退出；按文件启动时隐藏资源管理器 ([`1a4e493`](https://gitee.com/jermaine/yate/commit/1a4e493e3685bf06f7ae4e82f5f0d3b3ffc26b24))
- 修复关闭窗格命令、按键冲突、手册搜索与中文字形 ([`e70dd15`](https://gitee.com/jermaine/yate/commit/e70dd15505ef4e5116390d752e0154e0f1e5389a))
- 修复 :enew 后欢迎页重复出现，改为一次性显示 ([`8477ec0`](https://gitee.com/jermaine/yate/commit/8477ec06c5269088923f0958098460bfce96b2d4))
  - :welcome 命令可手动唤回欢迎页
- 修复终端面板无法用键盘关闭：识别真实的 Ctrl+grave 键名 ([`9ea2ac5`](https://gitee.com/jermaine/yate/commit/9ea2ac5fc4a02fa375797c8a42b83b4f4b9e4fd7))
- 退出时干净拆解后台服务，避免打印 traceback ([`f0da8b2`](https://gitee.com/jermaine/yate/commit/f0da8b286d113d46d550c983ef88a305110983e5))
- 仅 vim 键位下用 : 打开 ex 命令行 ([`9b76ae4`](https://gitee.com/jermaine/yate/commit/9b76ae4ccc8be426d2706577a9447fe94a9e0e9b))
- 修复终端面板布局晚于启动时丢失 PTY 早期输出 ([`3ca822c`](https://gitee.com/jermaine/yate/commit/3ca822c663403214336b33575d6a452683e8d1b5))
- 修复主题背景色；资源管理器支持键盘操作 ([`27b267c`](https://gitee.com/jermaine/yate/commit/27b267cbb99d135319eefaad64eba2c3e3132275))
  - ctrl+b/ctrl+e 开关与聚焦，a/A 新建、r 重命名、d/Del 带确认删除
- 修复编辑器视口跟随光标并支持滚动 ([`e28de3c`](https://gitee.com/jermaine/yate/commit/e28de3c09b649cfe90ac4ed280b9168d8efbb6f6))
- 修复 Nerd Font 图标、提示符回显与重复标签栏，新增欢迎横幅 ([`bf2b06a`](https://gitee.com/jermaine/yate/commit/bf2b06a99c13fa63e8fa4d84ab8c0ce11f9aa8d8))
  - 命令面板默认键改为 ctrl+shift+a，ctrl+shift+p 被 Windows Terminal 占用

### 性能优化

- 移动光标时保持语法配色 ([`2b8b737`](https://gitee.com/jermaine/yate/commit/2b8b73748ef182dbf3921b65a51e8788331247a1))
- 阻塞操作移入后台线程，保持界面流畅 ([`fd48e3c`](https://gitee.com/jermaine/yate/commit/fd48e3cb6d14a20b129ab1e328f35fe1502731ed))

### 重构

- 重命名 controllers 为 app_features、explorer_files 为 explorer ([`94d78c0`](https://gitee.com/jermaine/yate/commit/94d78c08400d9ea022e89ec6d1df80bd1bbd1e66))
- 重命名 app_parts 为 controllers，去掉 *_ops 模块名 ([`e5f847b`](https://gitee.com/jermaine/yate/commit/e5f847b4d825311a5f5ba9db280e589d3d991e7a))
- 把 YateApp 的协作方拆到 yate.app_parts ([`26076fd`](https://gitee.com/jermaine/yate/commit/26076fd856ee115ccb109ed084347f5cb5b27bcd))
  - 内置 ex 命令表、补全控制器、资源管理器增删改与终端生命周期独立成模块，YateApp 保留同名薄委托

### 文档

- README 与手册补充变更日志入口 ([`2490bb3`](https://gitee.com/jermaine/yate/commit/2490bb3301edaab5693f2e508126d184d2782faf))
- 生成 v0.1.0 双语变更日志并接入发布工作流 ([`fc74d5f`](https://gitee.com/jermaine/yate/commit/fc74d5f669fa103c0854357e47f5ef6d775235b4))
- 双语手册同步最新功能 ([`8b17bf1`](https://gitee.com/jermaine/yate/commit/8b17bf1ca75add80441eecf7c38fc43f1984a3ee))
- README 顶部醒目展示双语手册链接 ([`b3b4e81`](https://gitee.com/jermaine/yate/commit/b3b4e81222b1fecefc1d8dca9af08cb5d6bff874))
- 新增扩展、主题与 LSP 配置指南 ([`bf46092`](https://gitee.com/jermaine/yate/commit/bf46092b6e99cbdc6161d4ee13ebc72c5d284a08))
- 帮助、欢迎页与文档补充集成终端说明 ([`475a650`](https://gitee.com/jermaine/yate/commit/475a650f9b2ec52ef153949c17d8dd4c4aaf9a62))

### 测试

- 补充变更日志门禁、运行时文档屏与 CLI 参数测试 ([`1060811`](https://gitee.com/jermaine/yate/commit/10608119b9d848a2025f3a870cedf7455a0e68b9))
- 加固 rc 语言服务器解析并覆盖声明式 LSP 路径 ([`3ad2a7e`](https://gitee.com/jermaine/yate/commit/3ad2a7ee9751ae3e6a588d75d737aea67649c9a3))
  - 拒绝仅由点号组成的文件类型并裁剪空白，11 条新测试补齐 yate/config.py 分支覆盖

### 构建与工程

- 为发布提交补充中文翻译 ([`6fa7663`](https://gitee.com/jermaine/yate/commit/6fa7663f9ea781576e1178778c7182f52f60bc7b))
- CI 拉取完整历史以支持变更日志门禁 ([`a1d81d6`](https://gitee.com/jermaine/yate/commit/a1d81d6117f51634654361a6993d29921b8c0c1b))
- 打包时刷新随包变更日志 ([`b0ca383`](https://gitee.com/jermaine/yate/commit/b0ca3838870208978a676daa94b1e9eec5357835))
- 为两条 CI 流水线添加变更日志新鲜度门禁 ([`1998c82`](https://gitee.com/jermaine/yate/commit/1998c82fbb4aa17972a60310bdfaa002d786925a))
- 项目版本改为从 yate/__init__.py 动态读取 ([`7b5dd93`](https://gitee.com/jermaine/yate/commit/7b5dd93b01d8fa9dc2bb5fe77e946e57f7e2860a))
- wheel 附带 docs/，安装后手册链接可解析 ([`7b62b6c`](https://gitee.com/jermaine/yate/commit/7b62b6c1c5cc0520fdbbd257b161810ea3e30813))
- 删除旧的未更名 manual.md ([`17a0259`](https://gitee.com/jermaine/yate/commit/17a0259c5ffade09f8937e0ec9892a27eaadd82a))

### 其他变更

- 新增 yate --diag 诊断命令并扩展 --version 输出 ([`b6d1071`](https://gitee.com/jermaine/yate/commit/b6d10711004e5d6303638151c838bbf552265c3f))
- 新增 vim 风格窗格分割与资源管理器过滤 ([`ecadd41`](https://gitee.com/jermaine/yate/commit/ecadd4162c2df393492fe316e6535d8e332355ac))
- 随包扩展遮蔽时告警；包内剔除字节码；修复 Windows 8.3 配置路径 ([`db93b52`](https://gitee.com/jermaine/yate/commit/db93b52af796ff953f9124a8314e881e39c35480))
- 新增 GitHub Actions CI（Linux/Windows 矩阵） ([`949ed01`](https://gitee.com/jermaine/yate/commit/949ed01791e3cca2dbc1955158c8fb52978d5a32))
- 新增 Gitee Go 流水线运行全量单元测试 ([`a2e3195`](https://gitee.com/jermaine/yate/commit/a2e3195f96b3413758dbae342618ae531e6b9d35))
- 把 PyInstaller spec 移入 pack/ 并用 SPECPATH 锚定路径 ([`f355a44`](https://gitee.com/jermaine/yate/commit/f355a44a6e1b7213570ef3b29a31671b5bae4662))
- 在 pack/ 下新增跨平台 PyInstaller 构建脚本 ([`28a2a41`](https://gitee.com/jermaine/yate/commit/28a2a41bde57715af650a9d235768d0f42810e88))
- 覆盖层命令清除旧状态消息，静默命令补回执 ([`93845b3`](https://gitee.com/jermaine/yate/commit/93845b353cdc1477b6c406aad7e9383f002fe526))
  - 成功命令统一用绿色；:term 显隐、:set terminal_height 与单标签 :bn/:bp 会给出提示
- 新增 onefile PyInstaller spec，产出独立 dist/yate.exe ([`7cdd551`](https://gitee.com/jermaine/yate/commit/7cdd55149eec892586fd7dcb7c819edae0dba236))
- 同步 README 与当前实现 ([`d2c49df`](https://gitee.com/jermaine/yate/commit/d2c49dfdb8850ed0faa21484e37c0878f410483a))
- 英文设为默认 README，中文改名 README.zh.md ([`3835554`](https://gitee.com/jermaine/yate/commit/3835554022e4e2b6ff0f042d3685a0f6e996620a))
- 文档与扩展随包捆绑进 yate，并接入 PyInstaller 打包 ([`783f491`](https://gitee.com/jermaine/yate/commit/783f49116ab521840474feaa94113f48afa4be87))
  - 新增 yate/paths.py 统一资源定位，自动加载捆绑扩展（可用 disabled_extensions 跳过）
- 初始提交 ([`f690bf7`](https://gitee.com/jermaine/yate/commit/f690bf7d5f8be18de9b74b4006fcd50d18fda0d7))
- 初始提交：yate 终端编辑器 ([`ef1d964`](https://gitee.com/jermaine/yate/commit/ef1d964ecc5366cd6bf4c3da943e2371608e748a))
