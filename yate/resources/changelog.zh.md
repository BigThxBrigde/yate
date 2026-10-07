# 变更日志

> 由 git 历史自动生成于 2026-10-07 · yate 0.2.10

## [0.2.10] - 2026-10-07 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.9...v0.2.10)

### 新功能

- 自动回滚失败的扩展 setup（A13） ([`a78d300`](https://gitee.com/jermaine/yate/commit/a78d3005f027009816c6d94e4645546cef13ce8d))
- 预览窗格默认宽度放宽到 60％ ([`41b05ec`](https://gitee.com/jermaine/yate/commit/41b05ecd73fa1e6015c101502b4520d01f040d15))
- 预览窗格默认宽度放宽到命令面板的一半 ([`31ed715`](https://gitee.com/jermaine/yate/commit/31ed715a4962c3621e25dad4d5b2997ed41d85ff))
- ctrl+p 新增语法高亮文件预览窗格 ([`d10010a`](https://gitee.com/jermaine/yate/commit/d10010a5575269758735a539d9b11eb6445d2d6a))
- 新增 file_preview 字典选项 ([`125ddda`](https://gitee.com/jermaine/yate/commit/125ddda863a4433c6c2cf48019506d29ad30fa96))
- 所有打包失败统一走带错误码的错误边界 ([`b16952c`](https://gitee.com/jermaine/yate/commit/b16952ca25a41e1ea6e74d534d9e3a9645cb3aba))
- 通过有界线程池翻译 wiki 并带错误码 ([`625d443`](https://gitee.com/jermaine/yate/commit/625d443527fc1a0171b83f02956033e5940a6f81))
- 新增稳定错误码与无堆栈回溯的错误报告 ([`7e8432f`](https://gitee.com/jermaine/yate/commit/7e8432f1bd795748a06a068343feb5d0fd2370a8))

### 问题修复

- close two holes in the callable-alias guard [缺中文] ([`39c11b0`](https://gitee.com/jermaine/yate/commit/39c11b080cfa2b9a22e001a1ab73ad3cbd312596))
- revert the lint job to the linux runner [缺中文] ([`4f0ca47`](https://gitee.com/jermaine/yate/commit/4f0ca4794a3c623a43f6336bb671139f2b35dfda))
- run the pyright lint job on a Windows runner [缺中文] ([`f0654cd`](https://gitee.com/jermaine/yate/commit/f0654cd988f3791a05c44f0048158c041585c16f))
- pin pyright analysis platform to Windows [缺中文] ([`7a7604b`](https://gitee.com/jermaine/yate/commit/7a7604b45d8f2aa248d8690c77d612df3cfe5a1d))
- follow the option table for the keymap rejection message [缺中文] ([`83f2dab`](https://gitee.com/jermaine/yate/commit/83f2dab31744ac4ccd94f3a494df7b768e5fb127))
- correct the alias contracts and narrow the callable-alias guard [缺中文] ([`6a36195`](https://gitee.com/jermaine/yate/commit/6a361952406b28d71200de01a19d15c6b49e36f6))
- degrade a missing :set apply handler to a warning (PR !61 M1) [缺中文] ([`3eee5f8`](https://gitee.com/jermaine/yate/commit/3eee5f80508729b5148818cd80d70da4994a4865))
- 分词失败时退回纯文本行预览 ([`e7c2f25`](https://gitee.com/jermaine/yate/commit/e7c2f25c8b65801681b05f86737f2b09c583a51a))
- 预览分词失败时优雅降级 ([`a9311bb`](https://gitee.com/jermaine/yate/commit/a9311bb62cc57bdd02faac1db7d6ea14dac99bb8))
- 有界回收不干扰 worker 终端 ([`23f536a`](https://gitee.com/jermaine/yate/commit/23f536a448abe1f716a4da599f3566adee6fabd2))
- 限定翻译线程回收并对齐排空输出 ([`6f036cd`](https://gitee.com/jermaine/yate/commit/6f036cdbd4090db3c3c7517aed1185eba769289a))
- 界定取消信号作用域并把页面管道交给其写入方 ([`f63f773`](https://gitee.com/jermaine/yate/commit/f63f773c46f509a295e5082567db2816025734d5))
- 运行被拆除时终止其等待中的翻译任务 ([`beaed68`](https://gitee.com/jermaine/yate/commit/beaed68a8ef33e7299048053f114a15feb402542))
- 在受保护区域内安装收集策略 ([`406a6cc`](https://gitee.com/jermaine/yate/commit/406a6ccc3e67c5c5010a2bb7934109bfff4267be))
- 在排空 worker 失败前恢复串行策略 ([`3e43179`](https://gitee.com/jermaine/yate/commit/3e4317983f15859d644f63caa1b287dbfa2ba74c))
- 修正 wiki 进度工作中的评审发现 ([`00124d8`](https://gitee.com/jermaine/yate/commit/00124d8e68b1c72516456a68efbc67ae0fe91800))
- 将控制台中断视为中断而非失败页面 ([`23b0d54`](https://gitee.com/jermaine/yate/commit/23b0d546cf52663ad1bbaf9085b6e63e7b122f94))
- wiki 翻译进度按页推进 ([`20ff035`](https://gitee.com/jermaine/yate/commit/20ff0359a03b604592792fd81c1c2249271875af))
- contents 目录缺失时令单文件夹构建失败 ([`106e47c`](https://gitee.com/jermaine/yate/commit/106e47c402e6aa06eb8286768a51a932c82aa763))
- 交付统一命名为 runtime 的跨平台 contents 目录 ([`0e30a38`](https://gitee.com/jermaine/yate/commit/0e30a38c491a906ac5660bf8d86d8074df502087))
- 扫描全部 exec 目标以核对排除包 ([`842f830`](https://gitee.com/jermaine/yate/commit/842f830c8d5b0f52e3acaf6edd347b6f6ae96f54))
- 仿照模块加载器缓存守护 AST 解析 ([`6618a15`](https://gitee.com/jermaine/yate/commit/6618a15a313aae11f4efc586295b4a25e90fffbb))
- 堵上第二轮评审发现的前提守护漏洞 ([`cb082c2`](https://gitee.com/jermaine/yate/commit/cb082c22f5953aa8408bc6064fe20ef4c7edb784))
- 关闭打包守护与元数据的评审发现 ([`a0d1813`](https://gitee.com/jermaine/yate/commit/a0d1813e40ef7ab653d4c5ad0af8391b857b3809))
- 将扁平单文件夹布局限定在 Windows ([`b5520be`](https://gitee.com/jermaine/yate/commit/b5520bed097974a58c2e5ea935370d2129ef490d))
- 从打包中移除 Pillow 并扁平化单文件夹布局 ([`527a65c`](https://gitee.com/jermaine/yate/commit/527a65c8e8d27d72bd791a818d48503086573133))
- 将不可用的 wiki 目标报告为带错误码的页面写入失败 ([`86adde9`](https://gitee.com/jermaine/yate/commit/86adde97ca9e0cc6fb62afa92ac49c9bbca6571e))
- Ctrl+C 取消排队翻译并让 worker 远离终端 ([`042a3ac`](https://gitee.com/jermaine/yate/commit/042a3ac94390ce2ea62a4574914ef843c027982a))
- 拆分拒绝屏保场景以消除死存储 ([`c7099d0`](https://gitee.com/jermaine/yate/commit/c7099d0e56a1e5fb8a1332427892de1ec64ae676))

### 重构

- name the callback aliases with PEP 695 type statements [缺中文] ([`e49099a`](https://gitee.com/jermaine/yate/commit/e49099a4025c1321b12ecf4a2f447d699b8f5478))
- 拆分加载器为 yaterc.py 并将 :set 改为表驱动（A8/A9） ([`8b529d4`](https://gitee.com/jermaine/yate/commit/8b529d418a9b57cc5eb60683a5349df5d3ff09b6))
- 将 9 个流程模块迁入 yate/flows 子包（A10） ([`7e928de`](https://gitee.com/jermaine/yate/commit/7e928de28ae96c8ec4f4804f342eaeb0b6636fa9))
- 收口 Textual 私有 API（A2） ([`304215a`](https://gitee.com/jermaine/yate/commit/304215a80317b0686ec53811e863d382eb27894c))
- 保持 editor_lsp 包根轻量（A1） ([`27e5b2a`](https://gitee.com/jermaine/yate/commit/27e5b2a9d2c41c93fedd209852199de1f2378590))
- 收紧预览注入与缓存清理 ([`0671f50`](https://gitee.com/jermaine/yate/commit/0671f50a9d92bc9a46690f7ca68845b2fd06b3ce))
- 移除页面状态中不可达的复制结论 ([`ebbd8d9`](https://gitee.com/jermaine/yate/commit/ebbd8d9583d4aeb7b769c8319c6184193e890f89))
- 为 wiki 进度行指定唯一属主 ([`a3541cf`](https://gitee.com/jermaine/yate/commit/a3541cfa620db1f2df2536c2664368d39c7ca328))

### 文档

- register the PR !62 AI teammate review [缺中文] ([`25bc0c0`](https://gitee.com/jermaine/yate/commit/25bc0c00e6a5d48146ccf5567585842d908bf2a3))
- record the stale smoke assertion and its repair [缺中文] ([`cdb7dc3`](https://gitee.com/jermaine/yate/commit/cdb7dc3897be9e10cf560ce8ed38cceeb0647a26))
- register the callback-alias guard as case 25 [缺中文] ([`30c3a6b`](https://gitee.com/jermaine/yate/commit/30c3a6bc6300dca309aa19255bd8bcf7331d96fa))
- record the Callable alias plan for IKJUWP [缺中文] ([`cc2c159`](https://gitee.com/jermaine/yate/commit/cc2c1596723eafbb6885c44dbfab6377ecb251a0))
- register the PR !61 AI teammate review (index #36) [缺中文] ([`bb7c7d1`](https://gitee.com/jermaine/yate/commit/bb7c7d1e7dc761bb3a2e87342e99d4882662dd62))
- sync the boundary rules with the audit-fixes reality [缺中文] ([`edee837`](https://gitee.com/jermaine/yate/commit/edee837de931f87090aea95c9fca39cf75f1ecd6))
- backfill the repo-audit-fixes execution record [缺中文] ([`710903d`](https://gitee.com/jermaine/yate/commit/710903dfac7104a4f095415b8bab3ff647d04a00))
- add the 13 zh translations for the audit-fixes commits [缺中文] ([`94b6c7f`](https://gitee.com/jermaine/yate/commit/94b6c7f4a07ae98812724eb088dd158be6ca6050))
- absorb the repo-audit-fixes commits [缺中文] ([`e305421`](https://gitee.com/jermaine/yate/commit/e3054213679725fc1e00f08c6ccdab95da798a75))
- 成文站外文档与应用内手册的权威分工（A16） ([`00f6b03`](https://gitee.com/jermaine/yate/commit/00f6b033d51c0b3d888ebcf601550ec2c8675bbb))
- 补录缺失中文翻译至清零 ([`abae30c`](https://gitee.com/jermaine/yate/commit/abae30ccb08ab64e7c855a174a2bd8b92f1a451b))
- 修正 registries 层级 docstring 并新增文件体量阈值处置政策 ([`9334a23`](https://gitee.com/jermaine/yate/commit/9334a23a7b97f114cebfdd038338605e1546ebb6))
- 为评审发现 A1–A20 落盘 repo-audit-fixes 方案集 ([`0fb54d0`](https://gitee.com/jermaine/yate/commit/0fb54d0fc9729da1af8dba4d4458de7566de166a))
- 登记 2026-10-07 仓库架构审计 ([`a4a7708`](https://gitee.com/jermaine/yate/commit/a4a7708cdc313931ef4312cbc7ac7ebed7ed6a7d))
- 提及 ctrl+p 预览窗格及其宽度默认值 ([`1d5b2de`](https://gitee.com/jermaine/yate/commit/1d5b2dec90370857bbdb476fb2449301c28587db))
- 登记 PR 60 第二轮评审 ([`21ea681`](https://gitee.com/jermaine/yate/commit/21ea6810ff8e4edd62c81ddd4c89607e81c828bd))
- 记录 dumb TERM 根因与复测通过结果 ([`271ba88`](https://gitee.com/jermaine/yate/commit/271ba888b6a46c58a8d9e3e8df06c2e2d4a8618c))
- 记录 PR 60 评审修复门禁结果 ([`14ec104`](https://gitee.com/jermaine/yate/commit/14ec10434ef116e9eff0d9080c609d99cf45ad7e))
- 新增 PR 60 评审修复计划 ([`bd0c1fc`](https://gitee.com/jermaine/yate/commit/bd0c1fcf7fe7f0639f8850a74a2b5e875d584a00))
- 登记 PR 60 首轮 AI 评审 ([`1b36369`](https://gitee.com/jermaine/yate/commit/1b3636992765933d24d02149324a2eeccf0a9ecc))
- 记录 ctrlp-preview 问题修复扫尾 ([`2e138a8`](https://gitee.com/jermaine/yate/commit/2e138a8780066177641aea6ca6937566e7f1d144))
- 记录评审结论与最终门禁数字 ([`9ffc35b`](https://gitee.com/jermaine/yate/commit/9ffc35b74964e4a50c2f5dbcfd3bec0852dbf466))
- 文档补充 file_preview 选项 ([`f7b3ac1`](https://gitee.com/jermaine/yate/commit/f7b3ac1ceebf218c3dca1c6ff474ffe8f51f3590))
- 为问题 IKJRGP 新增 ctrlp-preview 子计划 ([`73ea9b6`](https://gitee.com/jermaine/yate/commit/73ea9b6ac1ef90bbe277a06851021456f1ab3e71))
- 登记 PR 59 第二轮评审 ([`d3ae09e`](https://gitee.com/jermaine/yate/commit/d3ae09e044dd97b094c7a5cde7947a9da970826d))
- 回填 PR 59 门禁数字与回滚的首个修复 ([`a1ac803`](https://gitee.com/jermaine/yate/commit/a1ac803dceac76d5e39ec4c708ca9deffed6879a))
- 登记 PR 59 机器人评审及其裁定 ([`f4fa387`](https://gitee.com/jermaine/yate/commit/f4fa38726e4effbde2ed76268185545ae40eef4d))
- 登记 wiki 打包评审第五、六轮 ([`cf5453d`](https://gitee.com/jermaine/yate/commit/cf5453d1bac12e90f980ccd9f813365063b4918c))
- 保持 skills 目录不动并在记录中说明 ([`f531fd0`](https://gitee.com/jermaine/yate/commit/f531fd011e952ff215314a248eda5badd82542f3))
- 将 yate 评审知识归档到 .trae/skills ([`90bd399`](https://gitee.com/jermaine/yate/commit/90bd3998859bbe7823042626a76886272256d573))
- 记录第四轮评审并闭环 ([`131adb9`](https://gitee.com/jermaine/yate/commit/131adb99299a7c3bd1e4414e232cf99cd5894b92))
- 说明 --translate-all 需要该钩子 ([`fe09ba9`](https://gitee.com/jermaine/yate/commit/fe09ba907caf50b9483dc32318f01229c5410293))
- 将技能评审轮次单独归档为评审记录 ([`2035243`](https://gitee.com/jermaine/yate/commit/2035243fccf5e338aab525e1b959977eea31959e))
- 写明重定向运行的实际输出 ([`377c004`](https://gitee.com/jermaine/yate/commit/377c00458440c9085ec1c689f6ba9bccc386ed56))
- 关闭首轮评审并登记第二轮 ([`28db1a6`](https://gitee.com/jermaine/yate/commit/28db1a696e8792e1197f03204599247d7fb8a631))
- 将技能评审发现登记为跟踪问题 ([`9981077`](https://gitee.com/jermaine/yate/commit/9981077791cdb6c96536817a30cdc8c88f715d9d))
- 记录控制台中断修复及其测量数据 ([`29df9f1`](https://gitee.com/jermaine/yate/commit/29df9f1ad11337d20376fb2413e4685601cbe79e))
- 修正 wiki 进度承诺与计划记录 ([`c50b0f9`](https://gitee.com/jermaine/yate/commit/c50b0f9bc2c7fea6f72048182fcd70e0336ef348))
- 统一 README 进度措辞并移除失效注入 ([`95ab4fa`](https://gitee.com/jermaine/yate/commit/95ab4fa8de3fe9176e39dfafdcd34796d313704e))
- 更新双语变更日志 ([`60c9545`](https://gitee.com/jermaine/yate/commit/60c95455e86f0b84e37eb6ecf4333449b7cd417d))
- 记录 PR 58 机器人评审及其唯一改进项 ([`419977a`](https://gitee.com/jermaine/yate/commit/419977a5e164324218517573c068a703dc9133e6))
- 记录提交归因偏差及相关裁定 ([`0518f4a`](https://gitee.com/jermaine/yate/commit/0518f4a7778b38e13a54a1585ce3063eaab1b483))
- 闭环统一打包布局第二轮评审 ([`60bd63e`](https://gitee.com/jermaine/yate/commit/60bd63e60006c76f63665c1c055a61a587bb9b87))
- 文档说明统一的跨平台打包布局 ([`dcf1f72`](https://gitee.com/jermaine/yate/commit/dcf1f723ce3da5a2d39c2cc38b1ed759b2c74f3a))
- 为 IKJPVB note_51452120 新增第二轮统一布局计划 ([`3b577fc`](https://gitee.com/jermaine/yate/commit/3b577fc6692d8ca16902cec0820cedc7374fb89d))
- 在最终评审小节补充真实构建验证 ([`fadd935`](https://gitee.com/jermaine/yate/commit/fadd935c10dfd84905afbbc19ec0823e7dd92d74))
- 以第四轮发现闭环 IKJPVB 评审 ([`f16180a`](https://gitee.com/jermaine/yate/commit/f16180afb4082d138116419988878771cbd86994))
- 在 IKJPVB 跟踪器登记第二轮发现 ([`4f68219`](https://gitee.com/jermaine/yate/commit/4f6821988115da6871645c1bf9b6f4f2e4ee6ac9))
- 跟踪 IKJPVB 评审发现及其处置 ([`217d2a7`](https://gitee.com/jermaine/yate/commit/217d2a72dd3d0168b2f44d4b7c03ecbd844a57aa))
- 记录打包布局的 python-code-review 轮次 ([`216a2c3`](https://gitee.com/jermaine/yate/commit/216a2c3cdde131ff3e55440c1725b5e759548626))
- 澄清 EXCLUDES 清单说明 ([`f0face8`](https://gitee.com/jermaine/yate/commit/f0face81e3eaee85d9bddb47f161b80a757afb1e))
- 在两份 README 与计划中记录 POSIX 布局修正 ([`a30550c`](https://gitee.com/jermaine/yate/commit/a30550c7c4997256ca032627eb1f51048e51b600))
- 回填 IKJPVB 门禁数字与评审轮次 ([`94ed6e5`](https://gitee.com/jermaine/yate/commit/94ed6e54c2c0e1582adede7a691207a316f194f8))
- 修正过期的 onefile 体积与中文措辞 ([`d25b111`](https://gitee.com/jermaine/yate/commit/d25b111a6fb8a95f88385d16ffd20d4d0e3b97c4))
- 文档说明扁平打包布局与移除的依赖 ([`d7f6a22`](https://gitee.com/jermaine/yate/commit/d7f6a22535d79f2b1f50fb3f131e17f32f04c387))
- 记录 IKJPVB 打包布局计划 ([`deb758b`](https://gitee.com/jermaine/yate/commit/deb758be9395564c9cf824da770193926227a165))
- 为三个规则文件添加 frontmatter ([`62ae99b`](https://gitee.com/jermaine/yate/commit/62ae99b43ca363c23affd171086da79b164de08c))
- 纯文档变更豁免测试门禁 ([`dbe2d81`](https://gitee.com/jermaine/yate/commit/dbe2d811c4643589d40f4932c6a873530a53b793))
- 将 skills 固定到 .trae/skills 并移除 .codebuddy 副本 ([`c34bbd0`](https://gitee.com/jermaine/yate/commit/c34bbd048cc7a82859b0af6e6239ca2670aadeb7))
- 登记 PR 57 第二轮 AI 评审 ([`8e13842`](https://gitee.com/jermaine/yate/commit/8e1384221a7fb71d6324d28e203451968fc80d67))
- 记录合并后门禁数字 ([`8f9f270`](https://gitee.com/jermaine/yate/commit/8f9f270891c6c046f38765e34581bc8076be18ad))
- 记录 PR 56 AI 评审轮次并刷新计划分支名 ([`db9f403`](https://gitee.com/jermaine/yate/commit/db9f4036f99b859b43598d6c3312358aaed0a051))
- 记录 IKJPEK 执行、门禁数字与评审轮次 ([`ccaca30`](https://gitee.com/jermaine/yate/commit/ccaca300014449bbf379f345c08d683fe7e5aa49))
- 新增 IKJPEK wiki 打包加固与并行翻译计划 ([`72a247f`](https://gitee.com/jermaine/yate/commit/72a247f299837e4b591c70651b63793fe9b5f1e6))
- 收尾 PR 57 评审事项并索引轮次 ([`be5a9ef`](https://gitee.com/jermaine/yate/commit/be5a9ef3ca94535c4768690b707140b6268469bb))
- 登记 PR 57 AI 评审并规划修复 ([`312a96a`](https://gitee.com/jermaine/yate/commit/312a96a81ef1a1175245bec63d6f88a7e89b9362))
- 回填扩充结果与场景陷阱 ([`5b93a4c`](https://gitee.com/jermaine/yate/commit/5b93a4cd6ecef211a2b73876630b636ac4893981))
- 新增冒烟测试扩充计划 ([`2ba17c5`](https://gitee.com/jermaine/yate/commit/2ba17c5ab5597da1aafe799816dbadf742bda9b7))

### 测试

- 使 wiki 实时显示免受 dumb TERM 影响 ([`cc4ebd6`](https://gitee.com/jermaine/yate/commit/cc4ebd60b605928e2a3ed887d545856f34c55ec7))
- 在预览宿主中禁用 Textual 内置命令面板 ([`9c08ffc`](https://gitee.com/jermaine/yate/commit/9c08ffcc0ec85522f8dddd2276e37269cc5dfc47))
- 新增 ctrl+p 文件预览场景 ([`ccb9fce`](https://gitee.com/jermaine/yate/commit/ccb9fce0262bdaba88b801345a8ad1853cd2ca8d))
- 从窗格常量推导收缩按键次数 ([`6a95fd8`](https://gitee.com/jermaine/yate/commit/6a95fd83a0a988e4bf7de2281b5f3045b97ddc94))
- 从注册表推导主题补全期望 ([`77475d8`](https://gitee.com/jermaine/yate/commit/77475d8c709074bf758314eaa2b1d11c9954ec11))
- 覆盖测试框架自身（基线、cli、不变量） ([`e8786aa`](https://gitee.com/jermaine/yate/commit/e8786aad7a6f7268cfef2684a5eb9251cfd1125d))
- 覆盖 vim 可视模式与寄存器路径 ([`09c4aa3`](https://gitee.com/jermaine/yate/commit/09c4aa39d714a1a60b54f8e33333caa97d987896))
- 覆盖资源管理器导航与窗格缩放组合键 ([`d186c26`](https://gitee.com/jermaine/yate/commit/d186c260290e235ddbaa342381ae44d61b283f73))
- 覆盖屏保，补上最后的动作缺口 ([`4a1c636`](https://gitee.com/jermaine/yate/commit/4a1c6361d2aac7b41e8d18d2f50df4be06cde4bb))
- 固化只读守护与静默失败提示 ([`c37c55b`](https://gitee.com/jermaine/yate/commit/c37c55bea22295f8d3460b59717afb69f0a4024e))
- 覆盖 diff 视图，补上最后的命令缺口 ([`bf9b197`](https://gitee.com/jermaine/yate/commit/bf9b197ef8021c475d279bf3e9574bbc8cad000f))

### 构建与工程

- replace CJK comments and docstring references with ASCII [缺中文] ([`65c152f`](https://gitee.com/jermaine/yate/commit/65c152fff3f0b66d94806ee0fa60106e834f044f))
- drop the --require-zh gate flag [缺中文] ([`36728aa`](https://gitee.com/jermaine/yate/commit/36728aa2cd7712e978f3fd9a1da50f0d57629753))
- 新增 pyright lint job、3.13 腿与 released-only 中文门禁（A4/A14/A5-2） ([`6100df0`](https://gitee.com/jermaine/yate/commit/6100df0de4b8b5c084d9ddf6cb74997447e593e1))
- 将散落资产迁出文档目录树 ([`3f7b3f7`](https://gitee.com/jermaine/yate/commit/3f7b3f77ddcbff1e2adb975f5865913b56f1614c))
- 从版本树移除误提交的提交说明文件 ([`2b78fd7`](https://gitee.com/jermaine/yate/commit/2b78fd724f8e1ec699f8992ed7fb69838f9ad022))
- 从版本树移除误提交的提交说明文件 ([`47b639f`](https://gitee.com/jermaine/yate/commit/47b639f8724c5660c0c6297f0630c9aa2f5a25ba))
- 重新截取两个屏保基线 ([`f9da8d1`](https://gitee.com/jermaine/yate/commit/f9da8d16279faf053e32c7492d3939a61a0ef63c))
- 为 14 个新场景添加基线 ([`fdfa2a1`](https://gitee.com/jermaine/yate/commit/fdfa2a1112baac3c9dde7390f095d7c51eb3fc74))

### 其他变更

- 将 5222 行应用 pilot 测试拆为九个功能域文件（A7） ([`fb030fd`](https://gitee.com/jermaine/yate/commit/fb030fdacb8ea0993021774757295825553a3306))
- 新增 dev/ts 依赖组守护测试并成文测试组织约定 ([`e97bec9`](https://gitee.com/jermaine/yate/commit/e97bec9de66f61bc39180106c163ddfdbbd6cc12))
- 回退「将 yate 评审知识归档到 .trae/skills」 ([`2016919`](https://gitee.com/jermaine/yate/commit/2016919a3d70162c4e4669b101535fa28354cae4))
- 守护收集策略结构与空操作开关 ([`d867588`](https://gitee.com/jermaine/yate/commit/d867588239239a96347a12a3e3a907a1d76f3aae))
- 断言迟到的失败可见而非仅入队 ([`3b00d88`](https://gitee.com/jermaine/yate/commit/3b00d88c53e0993488a31e7f0cdb91a5441b5eb3))
- 为评审修复加守护，并修复一个形同虚设的守护 ([`cf94290`](https://gitee.com/jermaine/yate/commit/cf942907c5c4120e8a34bacabc4118b32d4bcda8))
- 固化 wiki 运行的控制台中断契约 ([`c4baa3e`](https://gitee.com/jermaine/yate/commit/c4baa3e6b4342b3d9bf0afa2f9d69d209fb8e3f5))
- 弥合 wiki 进度守护中的评审缺口 ([`256173d`](https://gitee.com/jermaine/yate/commit/256173d40b107922d703ddf06d6e5fc2090868c3))
- 固化 wiki 生成器逐页进度刷新 ([`73c8cb2`](https://gitee.com/jermaine/yate/commit/73c8cb2c13a5150fa2a4d02a0720d22d41974529))
- 将单文件夹布局固定为命名的 contents 目录 ([`3914673`](https://gitee.com/jermaine/yate/commit/391467335e3f71a0686242490a0caa464268ac93))
- 固化共享排除清单与扁平单文件夹布局 ([`9730874`](https://gitee.com/jermaine/yate/commit/9730874c36206ce85016ca56fd7f2b689bc64f38))
- 证明中断不会排空翻译线程池 ([`4c7ed16`](https://gitee.com/jermaine/yate/commit/4c7ed16ac30e853b665cd85b1df1b5413c066425))
- 覆盖带错误码的错误边界与翻译线程池 ([`f2fbd81`](https://gitee.com/jermaine/yate/commit/f2fbd81c38bbaba88a92b791e820a8947580d5f9))
- 断言冲突错误码与新增 jobs 参数 ([`033f530`](https://gitee.com/jermaine/yate/commit/033f5302105cef9bb45e1840eb199a7225c97748))
- 将英文小节标签移入常量区统一存放 ([`e9aefbc`](https://gitee.com/jermaine/yate/commit/e9aefbc56916ccdf206365bd37aee06c1204d19b))

## [0.2.9] - 2026-10-05 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.8...v0.2.9)

### 新功能

- 键入统一走 type_char 并新增 vim 缩进键 ([`25c401c`](https://gitee.com/jermaine/yate/commit/25c401c717f1d750641ca45950a87c28532f3e27))
- 新增成对符号补全与 python 自动缩进 ([`4291b28`](https://gitee.com/jermaine/yate/commit/4291b28758ed9bfce3dbb229022e158b6b1af36c))
- 新增 batch/ini/fsharp/git/diff 语法示例扩展 ([`0497d39`](https://gitee.com/jermaine/yate/commit/0497d393d24060e8f08849bba28196fc87c4f8af))
- 为 23 种语言新增 22 个 tree-sitter 语法包 ([`8aea808`](https://gitee.com/jermaine/yate/commit/8aea808481deaee8ee5cf0c8c67b22318c8c9c35))

### 问题修复

- 使 vim 计数位移按行跨度生效 ([`5c41d69`](https://gitee.com/jermaine/yate/commit/5c41d69d7c91fac6ff4c40e39519ad3326916bc7))
- vim 缩进绑定改用 shift 键集合 ([`07b674c`](https://gitee.com/jermaine/yate/commit/07b674cc989ff0a9792b8fa322194bebeb34d247))
- 缩进切片保持仅向左并移除无用辅助函数 ([`17b617c`](https://gitee.com/jermaine/yate/commit/17b617cdf5e67674efab5a3e664efc28b3efe162))
- 从代码中删除最后一条失实的 regex 回退承诺 ([`3d1ed13`](https://gitee.com/jermaine/yate/commit/3d1ed13dec24bf712b0b5db4a083ba8edd6b0883))
- 类选择器不落入连字符名回退 ([`c3bcc07`](https://gitee.com/jermaine/yate/commit/c3bcc071a55672d0960151f8287262297c38aafe))
- 恢复连字符标识符改动损失的着色 ([`0d0e0c1`](https://gitee.com/jermaine/yate/commit/0d0e0c19a888e7bc5f4cf605cca63046b9253bf5))
- 修正随包示例模板的表述 ([`43fe08f`](https://gitee.com/jermaine/yate/commit/43fe08fc9e55642c118b86b492503114ae71c3d9))
- 用单一共享辅助函数截断文件类型候选列表 ([`8884e6f`](https://gitee.com/jermaine/yate/commit/8884e6fc0f54e3c38f7b3f9ff3ae84659703e193))
- 登记缺失捕获并使同跨度并列可判定 ([`9dbb5d6`](https://gitee.com/jermaine/yate/commit/9dbb5d6d43af4d38f8633cdfed6a156e8fc2fe35))
- 加固 smoke/changelog/wiki 工具并去重仓库根与规格逻辑（R-47..R-56、R-66） ([`ad7619a`](https://gitee.com/jermaine/yate/commit/ad7619a81c5afdd4beffa59afff0d65bf0fbaaef))
- vim 计数与寄存器语义、扩展类别及工作区缓存（R-57..R-65） ([`5c51180`](https://gitee.com/jermaine/yate/commit/5c511804126584a0f5a0a27df3df87c0c8bae71b))
- 增量 UTF-8 解码、escape 中止与共享修饰键表（R-39..R-46） ([`c8293d9`](https://gitee.com/jermaine/yate/commit/c8293d92857704651c0d0d9224848334a55c97e0))
- 防御性诊断、UTF-16 位置、下方粘贴与解析器上限（R-32..R-38） ([`22ca26e`](https://gitee.com/jermaine/yate/commit/22ca26e7e0f049aef79fbe6a1f25a111c25c0266))
- 命令面板光标键、渲染路径分桶与主题辅助（R-20..R-31） ([`11b4a9d`](https://gitee.com/jermaine/yate/commit/11b4a9d39dac75ea95f9da265ac0e753b03be827))
- 统一路径解析、补全前缀与拆分回滚（R-09..R-18） ([`5a25613`](https://gitee.com/jermaine/yate/commit/5a25613c0ad2fcd87883a906c28d31fd916793c3))
- 守护 dist 元数据、rc 提取、会话路径与树操作（R-01..R-08） ([`90ad524`](https://gitee.com/jermaine/yate/commit/90ad524401eed08468090bc16323fba9cb1fc09b))

### 文档

- 修正 12 份可见文档中的 29 类漂移 ([`195c20a`](https://gitee.com/jermaine/yate/commit/195c20a11053e29657624985e9e1ca23e6cf0793))
- 回填评审索引并记录 2026-10-05 文档扫查 ([`93d8c45`](https://gitee.com/jermaine/yate/commit/93d8c456cce12847114cbb320dea35f98574cb39))
- 使计划树符合 doc-conventions 并标注状态 ([`7f37512`](https://gitee.com/jermaine/yate/commit/7f375127f1e9e8ce91fc5890e65fc31831963d20))
- 新增 PR #54 第二次 AI 评审记录 ([`5383a82`](https://gitee.com/jermaine/yate/commit/5383a827e9fd19f9aeb8faeca40aa82aa7606afb))
- 移除无关文档 ([`6937900`](https://gitee.com/jermaine/yate/commit/693790046044177f48af09c620d6bcefb2b78bd6))
- 回填 PR #54 评审修复结果 ([`620429b`](https://gitee.com/jermaine/yate/commit/620429b5203c1433f6383185954fb53c1659fc2b))
- 规划 PR #54 评审修复 ([`d1d1a41`](https://gitee.com/jermaine/yate/commit/d1d1a4129eb823103593329326b7dd347ffd9a70))
- 登记 PR #54 对 enh/input-assist 的 AI 评审 ([`4b81e54`](https://gitee.com/jermaine/yate/commit/4b81e541190075c5203d8ca09fcb7d54ff9727ea))
- 新增 22:00-06:00 无人值守时段旁路规则 ([`ebf78e9`](https://gitee.com/jermaine/yate/commit/ebf78e9709f32c43c644997735bb1c38843576ae))
- 记录评审修复执行 ([`37584d6`](https://gitee.com/jermaine/yate/commit/37584d63d14e1610f9303d1f0f2c072225a5c259))
- 使空行缩进措辞与代码一致 ([`52a566c`](https://gitee.com/jermaine/yate/commit/52a566c77f686b40cf5a2d9f735b9efb2ca86bdd))
- 回填执行记录与偏差 ([`0e3f874`](https://gitee.com/jermaine/yate/commit/0e3f874c14e79f7416ab1cfcc8475247109847e7))
- 文档说明输入辅助与缩进按键 ([`7c15ab1`](https://gitee.com/jermaine/yate/commit/7c15ab181730d0e4d14ea0a70e815a33d0ef3c23))
- 新增输入辅助实现计划 ([`0809419`](https://gitee.com/jermaine/yate/commit/0809419552cb33ec0effb627f372be0e72e9d1f0))
- 记录智能体技术选型与工具调用守护 ([`0187074`](https://gitee.com/jermaine/yate/commit/0187074ad602408cd6604e1bac117da037ea177a))
- 登记 Gitee PR #53 的 syntax-langs 评审 ([`69b7f6f`](https://gitee.com/jermaine/yate/commit/69b7f6fe8ac573e676dc8691f6f0cd7c8e63eb9d))
- 记录第 3 轮评审与最后的已知限制 ([`4474d35`](https://gitee.com/jermaine/yate/commit/4474d3570f870067b5825537265d33097a2343f4))
- 记录第 2 轮评审与剩余已知限制 ([`ef83c81`](https://gitee.com/jermaine/yate/commit/ef83c817f2c504e3ee867094b22e5ca8b45a4f17))
- 删除最后一条 regex 回退承诺并修正语言计数 ([`26fc624`](https://gitee.com/jermaine/yate/commit/26fc624ef812a4bd2659ee0cb3a0ee9b5cc93b4a))
- 记录 syntax-langs 评审修复并回填计划 ([`0867015`](https://gitee.com/jermaine/yate/commit/0867015ce853e43b4c8bee7f0c47bce811ecca4d))
- 使文档与引擎实际行为对齐 ([`be243e9`](https://gitee.com/jermaine/yate/commit/be243e95fe4b5b2324588a6921b23f9ef793ce89))
- 记录 syntax-langs 分支评审与计划审计 ([`c67c382`](https://gitee.com/jermaine/yate/commit/c67c38281ef8a56c29cfb352e5e53cb59194b29c))
- 回填真实门禁数字到执行记录 ([`2ec7e6f`](https://gitee.com/jermaine/yate/commit/2ec7e6fc89153df036d8979e5fec66175df51a09))
- 文档说明内置语言集与新示例模板 ([`ea28852`](https://gitee.com/jermaine/yate/commit/ea28852d05bb487f3f5d9074f9404c4d8852e7dd))
- 为问题 IKJLTB 新增实现计划 ([`b8c3767`](https://gitee.com/jermaine/yate/commit/b8c376767102b0873ac898b620283809249a8b3d))
- 新增 AI 聊天智能体集成规格 ([`8eb1093`](https://gitee.com/jermaine/yate/commit/8eb109351b27ea84e0641c47a0e6cb8aa1e885d8))
- 登记 PR #52 AI 评审发现（note 51438554） ([`810d421`](https://gitee.com/jermaine/yate/commit/810d421005d95e1a7878e3d81164845be7372ad1))
- 回填 python-code-review 处置与索引（82/83 已修复） ([`7ad493a`](https://gitee.com/jermaine/yate/commit/7ad493af1f2d4e31d99708b482961169dab6ad45))
- 新增超过 100 次请求上限后继续的硬性规则 ([`3fe93c6`](https://gitee.com/jermaine/yate/commit/3fe93c60afac4c6ca315e5ec11fad4629646c373))
- 新增 python-code-review 修复计划（83 项发现处置） ([`6361b3d`](https://gitee.com/jermaine/yate/commit/6361b3d2130660134296b237b471923e5236caef))
- 新增 2026-10-03 全量 python-code-review 报告（83 项发现） ([`fb3242b`](https://gitee.com/jermaine/yate/commit/fb3242bff2c99b283329ba755cb51495199539ae))

### 测试

- 将计数位移固化为按行计数 ([`ca6d204`](https://gitee.com/jermaine/yate/commit/ca6d20412ee46d073d7b66552f7d2242bd176a6f))
- 覆盖含尾随空格行后的自动缩进 ([`9fbd03d`](https://gitee.com/jermaine/yate/commit/9fbd03d0e749e4db0426c678f3eafe4b0c59720a))
- 覆盖配对、跳过与缩进行为 ([`240bb25`](https://gitee.com/jermaine/yate/commit/240bb258efd205022a5ba57aeeab337ab9c03d99))
- 将类选择器守护放宽为子串语义 ([`0a5f2b1`](https://gitee.com/jermaine/yate/commit/0a5f2b14d788fdb7850ffc37b19880d1448e2d28))
- 固化类选择器回归与语言计数 ([`83df505`](https://gitee.com/jermaine/yate/commit/83df50542267e36f2d1eecc410d7b7e1bd4038da))
- 扫描字符串而非重写随包查询 ([`4c5c3e9`](https://gitee.com/jermaine/yate/commit/4c5c3e9a2c3693b21880ced0c53e662a69187a1f))
- 覆盖第二轮修复并加固捕获扫描 ([`0ec0920`](https://gitee.com/jermaine/yate/commit/0ec0920ba2cc0d1571084779948b946950b0d963))
- 守护捕获名、打包清单与模板 ([`5fb9003`](https://gitee.com/jermaine/yate/commit/5fb9003e2b3ecba428022ac5ed24b76a3d37b6bf))
- 覆盖新内置语言包与 regex 回退 ([`08a6396`](https://gitee.com/jermaine/yate/commit/08a63966bb285fa3fb64e9cd3890b4166fa8d905))
- 以轮询防抖重算替代固定 sleep（R-72，文件归属有误） ([`486401e`](https://gitee.com/jermaine/yate/commit/486401eb8ab5420c243d2e1c3e8358cbfb2cfff5))
- 锁定 lsp UTF-16 与防御性解析、下方粘贴及命令面板光标修复 ([`867acea`](https://gitee.com/jermaine/yate/commit/867acea25a36cf9c28b5d488311c2897a1b5dd14))
- 修复断言位置、不稳定 sleep 与同义反复断言（R-74..R-76、R-78..R-83） ([`036073b`](https://gitee.com/jermaine/yate/commit/036073b10ab7a9fbdfb98e556d8a403cbdc5cbd3))
- 修复主题泄漏与退出泵盲区，用 conftest 去重测试辅助（R-67..R-73、R-77） ([`bea5e6a`](https://gitee.com/jermaine/yate/commit/bea5e6a218a92ccba6d477e9c197f5e367b7601b))
- 锁定 split-utf8、escape 中止、共享修饰键、Windows shlex、探测与 vim 计数修复 ([`c07b9b5`](https://gitee.com/jermaine/yate/commit/c07b9b5a2c956a28a16b0c4762d177b74bb1ca0b))

### 构建与工程

- 移除测试注释中的真实机器路径 ([`2aa4e5f`](https://gitee.com/jermaine/yate/commit/2aa4e5fda2fe852a81f098d3742efb994e501b0c))
- 移除误留的 pytest 输出产物 ([`857a11a`](https://gitee.com/jermaine/yate/commit/857a11a85893c9f0e7bd1f54ae0dc3be2a7a728e))

## [0.2.8] - 2026-10-03 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.7...v0.2.8)

### 新功能

- 将 diff 视图接入命令、覆盖层与 cli ([`9103f27`](https://gitee.com/jermaine/yate/commit/9103f2780e2534d00af8360887d07ccfae35b090))
- DiffScreen 新增带窗格与编辑模式的 diff 视图 ([`bd3147a`](https://gitee.com/jermaine/yate/commit/bd3147ab2ee84bf0143c4240f18418851897173a))
- 新增支持行、词与三方合并的 L0 diff 引擎 ([`58a1da9`](https://gitee.com/jermaine/yate/commit/58a1da9b035e7d39e82368ad78b08dd75f67f71b))
- Rich 翻译进度展示与干净的 Ctrl+C 退出 ([`6a03d6b`](https://gitee.com/jermaine/yate/commit/6a03d6bd87c433d18bcc3c99ebd5a3008b8f9531))
- 默认 hy3，回退 glm-5.3-flash ([`24cf85a`](https://gitee.com/jermaine/yate/commit/24cf85a074aeee5d4b5bdd33c3c2a53ca4af8622))

### 问题修复

- 重新生成变更日志以落定状态 ([`844e1f2`](https://gitee.com/jermaine/yate/commit/844e1f2de8d8960cc5ff6e09fa76b9abc3da91ad))
- 拆分 ex 参数时保留内部空白 ([`7a91c80`](https://gitee.com/jermaine/yate/commit/7a91c80ff42bec6b36d14102cc0634901d663715))
- ex 命令行解析带空格的引号路径 ([`d7b84be`](https://gitee.com/jermaine/yate/commit/d7b84be988a9023ddb80585e4944018294d5cf69))
- 在编辑键表中解决积压项 S2、S3 ([`f78f65b`](https://gitee.com/jermaine/yate/commit/f78f65b1e60a5bc25b834efd90f205c139ed66ad))
- 将第二轮评审修复应用到 diff 屏幕 ([`8770b9f`](https://gitee.com/jermaine/yate/commit/8770b9f6ae191ed5b8be4dfb2b0837130652850d))
- 加固 open_diff 文件校验并新增评审测试 ([`4999ac9`](https://gitee.com/jermaine/yate/commit/4999ac985e5682447c054f871fb0014303151e2d))
- 处理预览与进度相关的评审发现 ([`19f44f0`](https://gitee.com/jermaine/yate/commit/19f44f0afc2eb902eed1ddf3eece4c6367cb740d))

### 文档

- 将 PR 51 机器人评审登记为评审记录 ([`704a773`](https://gitee.com/jermaine/yate/commit/704a773afefbc5e641e98086297056a6f4f368fd))
- 回填路径空格处理结果与 S5 闭环 ([`6073ef6`](https://gitee.com/jermaine/yate/commit/6073ef6f7298c054fc07f97f7057e37fcb7f0c2e))
- 为问题 IKJK0B 新增路径空格处理计划 ([`e7da154`](https://gitee.com/jermaine/yate/commit/e7da154bca5593e82fb13c63b86862d97a820522))
- 将 PR 49 机器人评审登记为评审记录 ([`f78ba0f`](https://gitee.com/jermaine/yate/commit/f78ba0f0daba04d7052621b36810d3c97eab3f9e))
- 回填 diff 工具条目并新增未发布区段 ([`18f266d`](https://gitee.com/jermaine/yate/commit/18f266db4212e05858e20900bc1a00648f2710ed))
- 登记 wiki 翻译进度评审 ([`9b173ef`](https://gitee.com/jermaine/yate/commit/9b173ef82d07f15d18205f2d54de28ddd45ac031))
- 仅登记 PR 49 机器人评审发现而不修复 ([`21d4dff`](https://gitee.com/jermaine/yate/commit/21d4dff841f1d6bfdefb615fe7322dd5c6874fea))
- 将积压项 W2 标记为已修复 ([`38266f2`](https://gitee.com/jermaine/yate/commit/38266f2128e0c0073ff827fa39ed9507e3da78c3))
- 将积压项 S2、S3 标记为已修复 ([`fb04d5f`](https://gitee.com/jermaine/yate/commit/fb04d5f0a2304f833121a705e453c25b89c8651c))
- 回填 diff 评审修复执行记录 ([`c5f8f02`](https://gitee.com/jermaine/yate/commit/c5f8f0273a8fec619f3d1dd6d1367cfb32da0ed6))
- 登记 diff 第二轮评审发现 ([`c06e789`](https://gitee.com/jermaine/yate/commit/c06e789fb9a70fe0e66b142c37dee3a8757e83f9))
- 新增 diff 工具实现计划 ([`e3b7bef`](https://gitee.com/jermaine/yate/commit/e3b7befc22b3a423d2d190a7d31075f0bca308f9))
- 回填 wiki 翻译进度执行记录 ([`a10d6ed`](https://gitee.com/jermaine/yate/commit/a10d6ed8b9109b61ad7aa02b2844e0aafbdd4a63))
- 新增 wiki 翻译进度计划 ([`2ac8453`](https://gitee.com/jermaine/yate/commit/2ac8453403e6c3282395fb2f630d704b34e91086))

### 测试

- 覆盖带引号与含空格路径解析 ([`528648b`](https://gitee.com/jermaine/yate/commit/528648b97c196e705c4b8e2b8f8c97bf36405896))

### 构建与工程

- 覆盖 diff 查看器剩余 W2 行为路径 ([`8d07460`](https://gitee.com/jermaine/yate/commit/8d0746039575d268403e1bcca23633729669ffe9))

## [0.2.7] - 2026-10-03 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.6...v0.2.7)

### 新功能

- 从 yate dist 元数据推导 [packages] 清单 ([`8d5ba7a`](https://gitee.com/jermaine/yate/commit/8d5ba7ab5e9f5eeca65396b1d5793ab4c7902614))
- 编辑器寄存器与系统剪贴板同步 ([`0f0252f`](https://gitee.com/jermaine/yate/commit/0f0252fea8f0eb84c2d65aeb8f02886abd3e2ea3))
- 暴露 api.sprites 支持自定义屏保字符 ([`2ac19ed`](https://gitee.com/jermaine/yate/commit/2ac19ed741a1f1966d39a231b69ff2ffa08f89b9))
- 翻转 wiki 翻译范围默认值并新增 --translate-all ([`0a9a4f9`](https://gitee.com/jermaine/yate/commit/0a9a4f9e8de76b5db9ade074ccfaeb79e7096ebc))
- 为 wiki 生成器新增 --translate-needed 开关 ([`9f11c0b`](https://gitee.com/jermaine/yate/commit/9f11c0b53691d4651a8d85b90a7d30b5c399b4ae))
- 经 codebuddy-code 新增翻译模块 ([`158c67a`](https://gitee.com/jermaine/yate/commit/158c67ad7eb465e5fee3fb54fd4bec77f849d7ac))
- 新增 wiki 生成器子模块 ([`0875261`](https://gitee.com/jermaine/yate/commit/087526110c5a67aa36d078c4cb21c2a8a67da7bc))
- 每个新任务要求独立 worktree ([`07fe1a6`](https://gitee.com/jermaine/yate/commit/07fe1a6982498088e072fc261cdbff0208cffc2a))
- 同带间隙超过距离下限即可复用行带 ([`af6dbf4`](https://gitee.com/jermaine/yate/commit/af6dbf49d16d39c173762c2bda0823aaee1c1dd1))
- 后继产生窗口可配置 ([`30e4d4a`](https://gitee.com/jermaine/yate/commit/30e4d4ae600ee54a45962251f0a9b85a982157a7))
- 游行队：多个互异精灵按全宽行走 ([`5353c9b`](https://gitee.com/jermaine/yate/commit/5353c9b575f2945161f6d510cce0771103ec014f))
- 新增全终端屏保与空闲触发 ([`6766bed`](https://gitee.com/jermaine/yate/commit/6766bed55e0766c01088cb6cab929107a052db4c))
- 新增 screen_saver 字典配置（enable/interval/switch/characters） ([`5937ce4`](https://gitee.com/jermaine/yate/commit/5937ce43630f4aabcf9b839d04ae4b9f93459dcb))
- 新增 pack rosters 子命令渲染阵容预览 ([`c019f22`](https://gitee.com/jermaine/yate/commit/c019f2235d94746edfa2b1a93b7ae1fb192c7bf8))
- 新增像素精灵包与洗牌注册表 ([`cb94b48`](https://gitee.com/jermaine/yate/commit/cb94b48dbb6887b20c8c4ef0306caac0601a6bc9))
- 实现 r 替换并修复行尾 a 与 V-y 光标 ([`c9f7cdf`](https://gitee.com/jermaine/yate/commit/c9f7cdf5ae7e7238b2e512f2988a0bb1eadfe87b))
- 新增 vim 文本对象 iw/aw、配对、引号与标签 ([`b63ebb8`](https://gitee.com/jermaine/yate/commit/b63ebb844dcfbb2bcb1ccd4ab5dcb24a58410ac5))
- 实现 find-char motion f/F/t/T 及 ;、, 重复 ([`c6f2677`](https://gitee.com/jermaine/yate/commit/c6f267784505b65b751a7bb8625569a9640b4c66))

### 问题修复

- 从 dist 元数据推导核心依赖名 ([`736c637`](https://gitee.com/jermaine/yate/commit/736c637107ffa172789b22bf795aa41424fd1fd4))
- 按渲染名计算 packages 列宽 ([`c9c8348`](https://gitee.com/jermaine/yate/commit/c9c834870d3fef8c313bebe0e4de5f23287b8970))
- pack.ps1 不再重定向原生 stderr ([`4d4735c`](https://gitee.com/jermaine/yate/commit/4d4735c0308b498c047b6ef8e12045e4a3588588))
- 随包附带核心依赖 dist-info 以支持冻结版本探测 ([`eb8d8af`](https://gitee.com/jermaine/yate/commit/eb8d8af34f5b542cad7ccf74a7bb07aaecef0598))
- 渲染 [packages] 前剔除空分组 ([`8ec8e92`](https://gitee.com/jermaine/yate/commit/8ec8e920786e084ecbe6253279addab66e3f25c3))
- 冻结构建随包捆绑 yate dist-info ([`79d41ac`](https://gitee.com/jermaine/yate/commit/79d41ac9dc6447c80dff4c50b8c446ad6f7a955b))
- 移除过期寄存器前缀并守护空剪贴板写入 ([`ec2606e`](https://gitee.com/jermaine/yate/commit/ec2606ea3fa21fad5b9a92f9ef69c74bb928ff6d))
- 只读缓冲区跳过寄存器预置 ([`64f5eeb`](https://gitee.com/jermaine/yate/commit/64f5eebc6eca1f8ecafb085d510db4edcc1f5a26))
- 进入插入模式与退出可视模式时清除待发寄存器 ([`ffdde7c`](https://gitee.com/jermaine/yate/commit/ffdde7c65570f8fffd5a435b82ccb833ea389262))
- 使管道往返测试桩符合 POSIX 可执行要求 ([`18b8098`](https://gitee.com/jermaine/yate/commit/18b8098941260f56d54b2ba42873eec467f39335))
- 深冻结运行时注册的帧与命令面板 ([`b084c17`](https://gitee.com/jermaine/yate/commit/b084c172a48589689ec628617cb5fd45a8f01d96))
- 行重同步感知 shift 并单遍穿线状态 ([`7f0d9c5`](https://gitee.com/jermaine/yate/commit/7f0d9c5805784a40cda5838c04df95a4f40bb5a4))
- 以行级 regex 重新分词消除行尾 token 闪烁 ([`fa71064`](https://gitee.com/jermaine/yate/commit/fa710642cfd8ae49c7d7fd6946d19a1861eb1cbb))
- ConPTY 派生期间持有句柄锁 ([`1394ff2`](https://gitee.com/jermaine/yate/commit/1394ff2b17c87867b4f6f034fa24ab3f3ea4360c))
- tree-sitter 构建受阻时仅告警一次 ([`ddfb18e`](https://gitee.com/jermaine/yate/commit/ddfb18ebc7d8b2bb0ca93786b1a29501e23c9bc8))
- 在收集与写入之间英文源被删时保持存活 ([`714183b`](https://gitee.com/jermaine/yate/commit/714183b0a78539f88a014825e519396d877e4c17))
- 任何另存失败都恢复只读锁 ([`17e2804`](https://gitee.com/jermaine/yate/commit/17e2804c97d0e4b03e0f6e6fe13bc83dcb52f02b))
- tree-sitter 降级到 regex 时仅告警一次 ([`aece343`](https://gitee.com/jermaine/yate/commit/aece343873b54d80755d76fae9f33def2611eaeb))
- 遏制补全解析失败 ([`9c8bd3a`](https://gitee.com/jermaine/yate/commit/9c8bd3abc85790c291069693c930b8f04643e57f))
- 用单锁串行化 ConPTY 句柄访问 ([`55e1055`](https://gitee.com/jermaine/yate/commit/55e105581689f5bc8e5ed115343d719777907c97))
- 修正 --translate-cmd 帮助并清理孤立 wiki 页面 ([`e0db927`](https://gitee.com/jermaine/yate/commit/e0db92735812023eb9dab7672a8a0585b7e5a913))
- 全量重译失败时保持清单干净 ([`1102f96`](https://gitee.com/jermaine/yate/commit/1102f96ec83c9c0277e12dbb8b6e34c8f8e40ddd))
- 强制 UTF-8 管道并按评审加固翻译模块 ([`62c6494`](https://gitee.com/jermaine/yate/commit/62c649457a8eef1af13e1b86c5ba985b32d50666))
- 处理第二轮 wiki 评审发现 ([`6709d22`](https://gitee.com/jermaine/yate/commit/6709d22a6475b117d534f7d99ec09712b2fe5b0d))
- 按评审加固 wiki 生成器 ([`a490d6f`](https://gitee.com/jermaine/yate/commit/a490d6fbc8ff84be40da6eb63ffcc36d5b5f6187))
- 为 github wiki 远程地址补 .git 后缀 ([`ebc6d98`](https://gitee.com/jermaine/yate/commit/ebc6d9886c9b1864e634f3ab035fbb12dcd2d23e))
- 移除遮蔽 ctrl+e 的重复 ctrl+shift+e 绑定 ([`6832024`](https://gitee.com/jermaine/yate/commit/6832024d70f240d3a7f2665fbf86fa26f1d11014))
- 将代码评审后续事项应用到 flow 模块 ([`8d1fb42`](https://gitee.com/jermaine/yate/commit/8d1fb423771301ba9bed584530a41353ad8fec5f))
- 收敛操作符区间端点并去重操作符复位 ([`c7c7f69`](https://gitee.com/jermaine/yate/commit/c7c7f69e795755d62f6d4633184263c2216a003b))
- 使 w、b、$ 与 G motion 落点符合 vim 语义 ([`43ee62d`](https://gitee.com/jermaine/yate/commit/43ee62d75ffc5d99112b8b2d81463183950c950e))
- e motion 落在词末字符 ([`df5a179`](https://gitee.com/jermaine/yate/commit/df5a179f44d604d81f1c1f1d7946291c6ff76939))
- 未知按键取消操作符并接受数字参数 ([`0ad1fdb`](https://gitee.com/jermaine/yate/commit/0ad1fdb92129345b02e5f48747d391c565e48386))
- 子代理文件对齐 Trae 规范 ([`b7b71f8`](https://gitee.com/jermaine/yate/commit/b7b71f8616e65df9fba1c3a26b715721bbfb2a6e))
- shuffle_order 拒绝采样加上限（PR #33 评审） ([`673da84`](https://gitee.com/jermaine/yate/commit/673da84d3546c916e38a6faa65d9c08ceb2cb7d8))
- 命令行输入不再误触 alt+shift+s ([`1862386`](https://gitee.com/jermaine/yate/commit/1862386764aeb0f171fe74916aad2b79f400edb6))
- shuffle_order 对不可救多重集保证终止 ([`00763fb`](https://gitee.com/jermaine/yate/commit/00763fbb7a1c99af88ab7ee578cd3dad0b715af8))
- 只读会话测试轮询 :e worker 完成 ([`0ea3711`](https://gitee.com/jermaine/yate/commit/0ea3711848f2d792a6c0dab890ba6039e22bbc93))
- 暴露测试安全的空闲轮询并修复空测试 ([`a538883`](https://gitee.com/jermaine/yate/commit/a5388835ffbd72386f9bca5cad6fbf58f7e96d86))
- 上报未知角色错误并守护白名单 ([`f5b2769`](https://gitee.com/jermaine/yate/commit/f5b2769ec4a0fecab1cd1dc97f832137b127f82a))
- 断言内容前先等待手动文档加载 ([`6f02578`](https://gitee.com/jermaine/yate/commit/6f02578476db3aff6817f32f369c80b9d97d746e))

### 重构

- 将 Requires-Dist 解析提取到 yate.dist_meta ([`2696aa1`](https://gitee.com/jermaine/yate/commit/2696aa15280b798fb4216fe7c2d2a038c0efb8c7))
- 将组件 DEFAULT_CSS 外置到随包 tcss 资源 ([`32d2f99`](https://gitee.com/jermaine/yate/commit/32d2f991011bec48f1ddb8f8fc2a49a5afaac03a))
- 进程内缓存随包 tcss 读取 ([`922e6f4`](https://gitee.com/jermaine/yate/commit/922e6f48477be2819d2da4e2077bf432bece3e47))
- 为模块级常量添加类型注解 ([`3a4d7da`](https://gitee.com/jermaine/yate/commit/3a4d7da4fd2009e886f69b13cab8a25170f7a3ff))
- 统一 import、文件末尾换行及小项风格修复 ([`eec9572`](https://gitee.com/jermaine/yate/commit/eec95726cba6830eaa1a6b8e43e84ca58b5f8c80))
- 补充缺失的类 docstring 与零星行级修复 ([`f88f05e`](https://gitee.com/jermaine/yate/commit/f88f05e77e25e4b898b9b81c7ae610c7b1b323cf))
- 收紧 HighlightProbe 文档类型 ([`68ad332`](https://gitee.com/jermaine/yate/commit/68ad33215ac1bcfac2f52dcd83050bf0b3ee7643))
- 将 devtools 桥迁至 logs 并外置屏保 CSS ([`2686635`](https://gitee.com/jermaine/yate/commit/2686635326f155afa7b7ca2016317323209ba568))
- 声明两阶段 flow 属性 ([`a4990c2`](https://gitee.com/jermaine/yate/commit/a4990c2f7edf3db9c934cbdac8d5e872ed136992))
- 提取扩展启动 flow ([`d1c1a2c`](https://gitee.com/jermaine/yate/commit/d1c1a2c3e07e9423e130919a20162847062dd2ee))
- 提取窗口窗格 flow ([`63717cf`](https://gitee.com/jermaine/yate/commit/63717cfaeeb9040f2d1be029bfafd589e2ab0688))
- 提取文档生命周期 flow ([`0cff320`](https://gitee.com/jermaine/yate/commit/0cff320b84c53bce4e47b0f6007687f37d60c084))
- 去掉薄委托与空壳，直接调用属主 ([`d634079`](https://gitee.com/jermaine/yate/commit/d634079bcccb1e58d87d7c7f00164a9176bd71d2))
- 统一 flow 模块命名为 *Flows ([`e6d32ac`](https://gitee.com/jermaine/yate/commit/e6d32ace24532abc7f2a9db7f4d81cdc83738dda))
- 提取提示符 flow ([`dd8a33d`](https://gitee.com/jermaine/yate/commit/dd8a33d0ff1d475fc7f54b371cad5788100e2211))
- 提取覆盖层 flow ([`ebc0657`](https://gitee.com/jermaine/yate/commit/ebc06572de6b2758d475eb5298ad074e28fe689a))
- 提取 shell flow ([`e7c9691`](https://gitee.com/jermaine/yate/commit/e7c9691d0a1a6eaa2c924af0ac69bd60b044d889))
- 提取 lsp_sync flow ([`6f564a6`](https://gitee.com/jermaine/yate/commit/6f564a61347652b7a0719e8701aa68263a1305da))
- 提取组装工厂 ([`80215c5`](https://gitee.com/jermaine/yate/commit/80215c52b72084aefd2a66093224b27d8b64bc14))
- 把 shuffle 重试预算提取为常量 ([`cd46611`](https://gitee.com/jermaine/yate/commit/cd4661194cd61ca4df2ccf1981354a5408403cba))
- 收紧空闲计时器时钟与产生簿记 ([`eccf33f`](https://gitee.com/jermaine/yate/commit/eccf33fb56dfc7bed9852d9d004475de1c580635))
- 结构化 operator-pending 状态与 c 操作符 ([`75d45c7`](https://gitee.com/jermaine/yate/commit/75d45c751f3caea1c0646167a27f981fc822f5c7))

### 文档

- 回填 PR47 评审修复结果与执行记录 ([`d13e454`](https://gitee.com/jermaine/yate/commit/d13e454175e7acf136a3d236e57188c7ba763036))
- 记录 PR #47 AI 评审发现 ([`fc5dd06`](https://gitee.com/jermaine/yate/commit/fc5dd06bd016c39b4cdbaeb2c2875ce986c47cad))
- 记录 PR47 评审修复计划 ([`28f4588`](https://gitee.com/jermaine/yate/commit/28f458835893570d8830519ce1c2a1eec2ff788f))
- 记录 pack.ps1 stderr 脆弱性修复 ([`cb67984`](https://gitee.com/jermaine/yate/commit/cb679840df1080bc859af509d4687bd94e8bb26e))
- 回填 diag-package-sync 执行记录 ([`07984cd`](https://gitee.com/jermaine/yate/commit/07984cd91b5fe83639096da7a6e878050c11e6f8))
- 采用 requires「yate」路线并过滤工具类 extras ([`a61f855`](https://gitee.com/jermaine/yate/commit/a61f855b00ad5282b62ec23fdefd7c96c9752ae9))
- 为问题 IKJJFI 新增 diag-package-sync 子计划 ([`c798cd9`](https://gitee.com/jermaine/yate/commit/c798cd980f5e9a2a789ac7341ad3616e498334ff))
- 登记 PR #46 AI 评审发现 ([`d910bf9`](https://gitee.com/jermaine/yate/commit/d910bf91147591b068cb31bfb8661783bcde3b78))
- 为问题 IKJHPH 新增 remove-inline-default-css 计划 ([`380fccc`](https://gitee.com/jermaine/yate/commit/380fccc151a6072a608f3e6fec7801776c5ae902))
- 登记 PR #45 第三轮机器人评审 ([`fe73f3a`](https://gitee.com/jermaine/yate/commit/fe73f3a8456de92a01849f5b71707410e2aa7987))
- 记录 PR #45 第二轮机器人评审 ([`f35dc88`](https://gitee.com/jermaine/yate/commit/f35dc889ef35428f9b12ce9ba405d3a6bc338fc0))
- 登记 PR #45 机器人评审记录 ([`baae1d8`](https://gitee.com/jermaine/yate/commit/baae1d8816c8a5396e5572881280eee321def0ad))
- 回填系统剪贴板计划的评审与定稿结果 ([`18e141b`](https://gitee.com/jermaine/yate/commit/18e141bb76f629fc9b29e910babf652ebff9e06c))
- 为问题 IKJHBO 新增系统剪贴板集成计划 ([`3e052dc`](https://gitee.com/jermaine/yate/commit/3e052dc19463e64ba590326605e363a5312cfd72))
- 以明确标准强制大任务拆分子计划 ([`0709e2d`](https://gitee.com/jermaine/yate/commit/0709e2d8b91ddbcf914c8d4442f70435ad3ba973))
- 登记 PR #44 机器人评审记录 ([`37515bd`](https://gitee.com/jermaine/yate/commit/37515bd3c8a55cad2ed763e36a373553a7b0b769))
- 恢复 tools docstring 中不配对的 RST 字面量 ([`56815e0`](https://gitee.com/jermaine/yate/commit/56815e0289911a20dce209121b107d7f7656611c))
- 回填 py-style-audit 执行记录 ([`6ffb0fb`](https://gitee.com/jermaine/yate/commit/6ffb0fb0887206ba233e40fb7949310548408a07))
- 为 yate 与 tools 补充 docstring 与理由注释 ([`52b22e3`](https://gitee.com/jermaine/yate/commit/52b22e38a841bd32db6d79d1e2acfe618a9f5e5a))
- 修复附录代码围栏标记 ([`da6ba8a`](https://gitee.com/jermaine/yate/commit/da6ba8ac7dcf5927f126eeb035e638213298b2c0))
- 新增 python 风格审计计划及探针发现 ([`c5476f8`](https://gitee.com/jermaine/yate/commit/c5476f8ecbbbf44938eb33191058dc42fa6a6248))
- 将 code-review-expert 切换到 python-code-review 技能 ([`0a8463e`](https://gitee.com/jermaine/yate/commit/0a8463ef0850a1503a26369a6a7ad7f943d23a9d))
- 登记 PR #43 机器人评审记录 ([`36ca034`](https://gitee.com/jermaine/yate/commit/36ca03481286f81461802aaf44612e3db6b9f7cf))
- 新增 shell 多行文本与 python 探针的杂项规则 ([`7a433e7`](https://gitee.com/jermaine/yate/commit/7a433e7a1f8cc26225fdefb1eca0f0dce06b88cb))
- 将 plan-before-execute 触发路由到 task-orchestration ([`e582034`](https://gitee.com/jermaine/yate/commit/e582034c269548f76f11589a1b8dcc889c1e5983))
- 将 coder 限定为子任务执行并遵守全部仓库规则 ([`a3a2a28`](https://gitee.com/jermaine/yate/commit/a3a2a28ad2f6a32e4440bd2b3e56c1f1354aa22d))
- 要求计划包含详细测试用例与验证方案 ([`c639876`](https://gitee.com/jermaine/yate/commit/c639876a630adddbd37e2fb65359784acc340b01))
- 回填评审与计划文档中的已执行状态 ([`bc97f7e`](https://gitee.com/jermaine/yate/commit/bc97f7ed104bcb13791859d3e362e53a430cc268))
- 在整改计划中记录第二轮评审 ([`17ec133`](https://gitee.com/jermaine/yate/commit/17ec1339a267d31570f07864035f3499281330c2))
- 将实现结果回填到 reviews-open-issues-fixes 计划 ([`c27be65`](https://gitee.com/jermaine/yate/commit/c27be6533681bb5424c83f8d9588c80bf37952fe))
- 使句柄锁注释与实际守护范围一致 ([`e3c7105`](https://gitee.com/jermaine/yate/commit/e3c71057a831cbad815a5dadce68b14345fdd826))
- 回填五个已关闭项的整改结果 ([`144931b`](https://gitee.com/jermaine/yate/commit/144931b2f4b1ae2f4f1c6edf9cfeed8010fde7a4))
- 写明半注册契约 ([`962666c`](https://gitee.com/jermaine/yate/commit/962666cc089275ff94349252e6d72284fe6291fb))
- 新增 reviews-open-issues-fixes 计划 ([`c52ebe0`](https://gitee.com/jermaine/yate/commit/c52ebe0b1f329b0bdcf432a3af44f2cb3a530645))
- 登记 PR39 第三轮评审发现 ([`82c8cae`](https://gitee.com/jermaine/yate/commit/82c8caed8bd1e589d6743411723ad72e3a75830f))
- 登记第三轮评审发现（双语 TOCTOU） ([`63e87d3`](https://gitee.com/jermaine/yate/commit/63e87d3536a665cb07bcf451b1c706409e7469d3))
- 从 wiki 示例中移除已删除的 --translate-needed ([`4954819`](https://gitee.com/jermaine/yate/commit/4954819b278e6b3c42f8ec0064b413e71ae7ed40))
- 将翻译范围开关文档更新为 --translate-all ([`01553b4`](https://gitee.com/jermaine/yate/commit/01553b4837666cc5e9483e2bbe4ca92052db3fd0))
- 文档说明 wiki 生成器与 translate-cmd 用法 ([`e7ea7d8`](https://gitee.com/jermaine/yate/commit/e7ea7d84329ba8ab53b8ef41b7c153b8c331f09c))
- 记录 translate-cmd 评审轮次 ([`3c873b9`](https://gitee.com/jermaine/yate/commit/3c873b9427aa1ebcbd205c6549a239137a5cd04c))
- 回填 translate-cmd 计划记录 ([`338520b`](https://gitee.com/jermaine/yate/commit/338520bd47013fd74df78a6c1876f78d9648c1d4))
- 从 translate-cmd 计划中删除本地安装路径 ([`ff244b3`](https://gitee.com/jermaine/yate/commit/ff244b339358cb433160cb54f423cf78fee4ffb0))
- 为 translate-cmd 设计 --translate-needed 开关 ([`c7877f5`](https://gitee.com/jermaine/yate/commit/c7877f58379c4e9cbf80d6137366f459247a6111))
- 在评审修复计划中记录第二轮提交哈希 ([`6a0f429`](https://gitee.com/jermaine/yate/commit/6a0f42966945d111c7bb90f77462044e739fee89))
- 回填第二轮评审修复记录 ([`cb6a7ba`](https://gitee.com/jermaine/yate/commit/cb6a7bae68e5fd00062d6ec3d4870c1ded0437e8))
- 登记 pack-wiki 评审修复计划 ([`450fdf6`](https://gitee.com/jermaine/yate/commit/450fdf6cb8ec9f84d3173b3f8caefb6409456295))
- 回填 pack-wiki 计划执行记录 ([`a0cef14`](https://gitee.com/jermaine/yate/commit/a0cef1406d72bf76e755732abb567a5f9689b5cc))
- 恢复 translate-cmd 钩子计划 ([`3761d6c`](https://gitee.com/jermaine/yate/commit/3761d6c88e72659ff172511eb493963eb118af64))
- 用内置免费 API 翻译器替换翻译钩子 ([`4d668ef`](https://gitee.com/jermaine/yate/commit/4d668efa9e78b595b443193ca46c0316ee4cd60e))
- 新增 pack-wiki 生成器计划 ([`a28c051`](https://gitee.com/jermaine/yate/commit/a28c051719b12b0e0a8a5116cf438694aacea1ef))
- 登记能力注入评审的已知取舍 ([`a8c2e69`](https://gitee.com/jermaine/yate/commit/a8c2e69aa87adc92ebf0a65a4c3945b22ce7ee6f))
- 记录该评审轮次及其三项修复 ([`d0d1638`](https://gitee.com/jermaine/yate/commit/d0d16382375261bf83483ce739e6cdbe9a0a1071))
- 用实测门禁数字回填执行记录 ([`5be93a8`](https://gitee.com/jermaine/yate/commit/5be93a84a147d731551e6c87d980426d5cc638a9))
- 记录语义能力注入及其守护 ([`cb6a43d`](https://gitee.com/jermaine/yate/commit/cb6a43dd10cfd3650f0fef87a227193a9de88346))
- 限制单个计划大小并净化真实路径 ([`7184ba2`](https://gitee.com/jermaine/yate/commit/7184ba2e7635cf19d977e075cae61b4acc8a8e8f))
- 重命名 editor-refactoring-plan 子目录 ([`919ec4d`](https://gitee.com/jermaine/yate/commit/919ec4db8ce68320aaeea63768ea5f5adb638ec9))
- 登记 PR40 机器人评审发现 ([`5bf4778`](https://gitee.com/jermaine/yate/commit/5bf4778c2e1df99754b754a840d65645f320e5e1))
- 要求新任务工作区重建沙箱 venv ([`9060c2c`](https://gitee.com/jermaine/yate/commit/9060c2c3a20c15827f8db426dad5a82bc8cf3505))
- 登记 PR38 机器人评审发现 ([`3f9e499`](https://gitee.com/jermaine/yate/commit/3f9e499c6aab966ff9d27651e0dcbc67e6eca594))
- 修正 venv 诊断并记录不稳定主题测试 ([`a429251`](https://gitee.com/jermaine/yate/commit/a429251443970e5fe6d15975bdb65cd7a8d8cb58))
- 记录 review-vscode-keymap 执行结果 ([`bf1b362`](https://gitee.com/jermaine/yate/commit/bf1b362163e3e73bb9e79346a94bf1cae8f7e564))
- 登记 Gitee PR 37 机器人评审 ([`e91d433`](https://gitee.com/jermaine/yate/commit/e91d4338856f89a6c7c206120d4707e1c0a56b8f))
- 记录 TRAE-code-review 第二遍 ([`0ab9e6d`](https://gitee.com/jermaine/yate/commit/0ab9e6de5a53685aa074bcfc419a21fd15a4a1d2))
- 回填编辑器拆分结果 ([`4050121`](https://gitee.com/jermaine/yate/commit/4050121bfb4caef82ae479e07fe1d1d07cafa483))
- 记录编辑器拆分评审 ([`c0787e5`](https://gitee.com/jermaine/yate/commit/c0787e5f7b69476974ef0fa9ba77278a109d4ebb))
- wave-2 后复核编辑器拆分计划行锚点 ([`1ff34d3`](https://gitee.com/jermaine/yate/commit/1ff34d3f595b211f4f5ac8addbb786450b93db62))
- 新增 editor-split plan-e 与 plan-f 子计划 ([`7c4b154`](https://gitee.com/jermaine/yate/commit/7c4b154fdc74292e12894466b9ecb532d54d0a51))
- 按命名约定重命名编辑器重构计划 ([`9a0f7a8`](https://gitee.com/jermaine/yate/commit/9a0f7a8168dff6ee1c9ce1166a76709f2592bace))
- 按职责而非 LspSync 异常命名 flow 模块 ([`783f187`](https://gitee.com/jermaine/yate/commit/783f187a6b30ca2f7f44e51cef1d323e365662c8))
- 新增 editor-split 计划文档 ([`1573bac`](https://gitee.com/jermaine/yate/commit/1573bacb0024257b730e7de330c9d2357de90df9))
- 回填编辑器重构结果与偏差 ([`09c4d24`](https://gitee.com/jermaine/yate/commit/09c4d24e1f5aec694468b79b03f1310f7935b124))
- 新增编辑器重构波次计划 ([`51e14ee`](https://gitee.com/jermaine/yate/commit/51e14eea543d73f635af183d68936caf8c994522))
- 将 doc-naming 更名为 doc-conventions 并强制相对路径 ([`a32f99a`](https://gitee.com/jermaine/yate/commit/a32f99afbf5e6f88f3834af9c1a0b99319e89cfe))
- 以 TRAE-code-review 技能作为评审入口 ([`4153dfd`](https://gitee.com/jermaine/yate/commit/4153dfd0084fb29b0c5b199a7f1e01a8d77b1e82))
- 在编码风格中加入 PEP 20 之禅与 pythonic 模式 ([`19a08ef`](https://gitee.com/jermaine/yate/commit/19a08ef747184c84c38041bbab8daf87a58c9daf))
- 将路径引用从 .trae/review 改指 .trae/reviews ([`e42170e`](https://gitee.com/jermaine/yate/commit/e42170e14cac01dd67d324474654dcb5d6d48e18))
- 将 .trae/review 更名为 reviews、.trae/wiki 更名为 wikis ([`ed5369e`](https://gitee.com/jermaine/yate/commit/ed5369e0e54c128edc4e8114525915df9a322402))
- 为闭环编排新增关键词触发 ([`539269c`](https://gitee.com/jermaine/yate/commit/539269c89c0c8ce61dc7fa6892d50e8bad5742b8))
- 更新中英双语变更日志，同步新增功能、修复、重构与文档内容 ([`4db462f`](https://gitee.com/jermaine/yate/commit/4db462f86f4d80438d66020a8424fba21a0d3a0e))
- 在评审 README 中索引 PR35 评审轮次 ([`58339d6`](https://gitee.com/jermaine/yate/commit/58339d6ed9dc82a23f3d209ec97a00e33af4e98c))
- 记录 PR35 评审发现与修复 ([`5fc7a28`](https://gitee.com/jermaine/yate/commit/5fc7a2802cd4ef236a2471be81896587c6f77463))
- 将 vim 键位计划更名标记为完成 ([`8a8202b`](https://gitee.com/jermaine/yate/commit/8a8202bc8b5acb198217ab8f4f068a51bec9ef8a))
- 将评审计划文档更名为连字符命名 ([`3350009`](https://gitee.com/jermaine/yate/commit/3350009365e78b0281f02ed73780b4844071fccb))
- 计划命名迁移后修复内部链接 ([`1f53486`](https://gitee.com/jermaine/yate/commit/1f5348676aae3e6310231e478ca75e3567921b01))
- 将计划命名从下划线迁移到连字符 ([`7b1b269`](https://gitee.com/jermaine/yate/commit/7b1b2692e86b80ff26299b8915680816d50c5c39))
- 回填 motion 修复执行记录 ([`6e33bc7`](https://gitee.com/jermaine/yate/commit/6e33bc7f849062486964711e3ed97c028395786b))
- 将计划文档更名为 doc-naming 约定 ([`2443da8`](https://gitee.com/jermaine/yate/commit/2443da8774efdb170c829aef47a2de1b5bf539d2))
- 为各代理添加链接 ([`4cea35c`](https://gitee.com/jermaine/yate/commit/4cea35cbfb10e4115f74adf371b267f0c177c72e))
- 覆盖评审记录与评审修复计划的命名 ([`6cd71ce`](https://gitee.com/jermaine/yate/commit/6cd71ceac00926152913535800dc906ebf36722f))
- 新增仓库级文档命名约定 ([`3a672ae`](https://gitee.com/jermaine/yate/commit/3a672ae32c17d1fe79263d257edcc8c1bbfed273))
- 在编排规则与 architect 代理中采用统一计划命名约定 ([`4ac4ace`](https://gitee.com/jermaine/yate/commit/4ac4acee921510f7e9a670837e3bbf2d52931160))
- 统一计划与子计划命名约定 ([`37ed3b6`](https://gitee.com/jermaine/yate/commit/37ed3b65334946f0791a70cc64488f0cb3a15c04))
- 关闭附录 B 待定决策 ([`b1024f5`](https://gitee.com/jermaine/yate/commit/b1024f5cd82291395de92ac439b2b2b5deffe35b))
- 将 PR #13 条目指向评审目录 ([`2862a3d`](https://gitee.com/jermaine/yate/commit/2862a3d1e61b513cdbcf7aa6283d11778efea4df))
- 对照代码校验计划文档并修复过期引用 ([`49240eb`](https://gitee.com/jermaine/yate/commit/49240eb89fc35a8350bb4909beee89fbcc69e397))
- 审查问题巨型文件拆分为带时间戳的 review 目录 ([`ca9b802`](https://gitee.com/jermaine/yate/commit/ca9b8025132823f53350d18c9a197298f9e68fc8))
- 移除无用的 links md ([`e6ca963`](https://gitee.com/jermaine/yate/commit/e6ca9633b3121c4a57971e45248cf466104fe9de))
- task-orchestration 要求每步提交但不推送 ([`da0896d`](https://gitee.com/jermaine/yate/commit/da0896d8dd8daf5067deaaae3cdbc6e9b3afd257))
- 记录 e motion 边界修复 ([`fa43c35`](https://gitee.com/jermaine/yate/commit/fa43c35873fa40ab5c0d1bafa25564f9b19c6c8e))
- 记录合并后分支评审修复 ([`ae3d0ed`](https://gitee.com/jermaine/yate/commit/ae3d0ed762ca3b7c33f80d3de1663453c644a1c0))
- 新增任务闭环编排规则 task-orchestration ([`f085a07`](https://gitee.com/jermaine/yate/commit/f085a07ab9af5718711f3c2be1dc4ec2cbfacbf9))
- 重新生成双语变更日志并回填中文 ([`d66ace9`](https://gitee.com/jermaine/yate/commit/d66ace9637c2ef1ca8fec2e8ebc75ccccf31a4a4))
- 新增 api.sprites 扩展注册方案 ([`1bd6975`](https://gitee.com/jermaine/yate/commit/1bd69752651e897a6a23173dab86eefd6f87a417))
- 新增 P1-P7 评审修复方案 ([`6380ae6`](https://gitee.com/jermaine/yate/commit/6380ae664d8e4eda981b718ecddb7d2c8a98d830))
- 新条目改用完整提交哈希 ([`834f25b`](https://gitee.com/jermaine/yate/commit/834f25bae5b62cc657d100945ed110a0348d32d4))
- yaterc、变更日志与方案同步同带距离规则 ([`b7ed339`](https://gitee.com/jermaine/yate/commit/b7ed3396088bb24ae5def38d3b93522e9bcb068e))
- yaterc.example 补屏保配置说明 ([`d50ecf7`](https://gitee.com/jermaine/yate/commit/d50ecf741ede3bad48558e688f84cf0f7002f584))
- 产生窗口的变更日志条目与方案回填 ([`11245f4`](https://gitee.com/jermaine/yate/commit/11245f4a446ecf933eb7848774e6a83866cdc03e))
- 方案文档嵌入阵容预览并移除过时 venv 行 ([`0348af2`](https://gitee.com/jermaine/yate/commit/0348af27759d9d1857f77774e60e9ecb92ee54f3))
- 回填评审修复结果与偏离记录 ([`86a7764`](https://gitee.com/jermaine/yate/commit/86a7764ea6a91c608acc5c95c9b7c5869b23c2b1))
- 新增屏保发现项的评审修复方案 ([`5eb3c72`](https://gitee.com/jermaine/yate/commit/5eb3c72cd3e9e02dfc5e8e877be92d8a1ee5a02d))
- 变更日志与方案记录游行队重构 ([`0a4435d`](https://gitee.com/jermaine/yate/commit/0a4435d65018004fc436cdcf55e75c1c67c99601))
- 回填 fancy_sym 实施结果与偏离记录 ([`a92d420`](https://gitee.com/jermaine/yate/commit/a92d420e5e2f2250a7552748bc277b69afbd33b3))
- 编写空闲屏保文档并致谢 that_editor ([`43a5c88`](https://gitee.com/jermaine/yate/commit/43a5c88317024e7f63de8a5bc7d2637ae32721f1))
- 新增 fancy-sym 屏保方案与子计划 ([`1ba5c53`](https://gitee.com/jermaine/yate/commit/1ba5c5380c5b8258158b6280340743044ff87ff2))
- 记录 vim 键位评审执行结果 ([`1a7a52b`](https://gitee.com/jermaine/yate/commit/1a7a52b37190660d8a6c82aa3b1669cf1672d2a2))

### 测试

- 守护组件默认 CSS 从随包 tcss 加载 ([`6c30674`](https://gitee.com/jermaine/yate/commit/6c306742051944454102a7bfd96264734c455e1a))
- 统一测试风格：docstring、续行与注解 ([`feaae60`](https://gitee.com/jermaine/yate/commit/feaae608023761dfa1a9bdf0c46fd2ebb4d546eb))
- 为 conpty 假件添加注解以通过 pyright 严格模式 ([`f490e28`](https://gitee.com/jermaine/yate/commit/f490e28da22819fcc63f5f1555014ae98ea6586b))
- 在 vsc 断言中指名重复的原始键 ([`3c1cee2`](https://gitee.com/jermaine/yate/commit/3c1cee20b9c00c1494831def225d93b22c03184f))
- 覆盖 wiki 生成器 ([`e6c9740`](https://gitee.com/jermaine/yate/commit/e6c97403d0a664eb9eb89542aeb6bd608a662179))
- 加固 App 下标守护并修正 docstring ([`f264058`](https://gitee.com/jermaine/yate/commit/f2640587e27f402a9114a3253052be77c6bda110))
- 架构守卫：App 注解精确化与流程模块禁持句柄 ([`de33c2b`](https://gitee.com/jermaine/yate/commit/de33c2bee1b0e05e5dbf4747211c7258aad2b319))
- explorer 测试适配 LspSync 的 spawn 动词 ([`98a1128`](https://gitee.com/jermaine/yate/commit/98a1128518f29a082eb9d0ceda738fbd188b032f))
- 跟随 LspSync.documents_closed 拆分 ([`d7f474f`](https://gitee.com/jermaine/yate/commit/d7f474f9c63b545b3aa9812d983370a2570083dc))
- 固化引号上光标判定并记录冒烟结果 ([`3c5a84c`](https://gitee.com/jermaine/yate/commit/3c5a84cd06214cdb62e92f1e4b5ef4e38423b980))

### 构建与工程

- 跟踪 CodeBuddy 主规则加载器 ([`7f7ccf9`](https://gitee.com/jermaine/yate/commit/7f7ccf97d9675a61b797ccfa518d613aa656470e))
- 补齐剪贴板覆盖缺口并修复 import 分组 ([`72020bb`](https://gitee.com/jermaine/yate/commit/72020bbc599d643af911d9288ba91af8e5c1bae0))
- 新增 coder → translator 智能体 ([`f080c0d`](https://gitee.com/jermaine/yate/commit/f080c0da2a690df3daba6147fb46ff66834dbd92))
- 移除 task-coordinator 子代理剧本 ([`30d7909`](https://gitee.com/jermaine/yate/commit/30d790938b2116b351e8b29eade0b3412e405405))
- 新增 plan-execute-review 代理团队定义 ([`af566a2`](https://gitee.com/jermaine/yate/commit/af566a2481f3c5510decdb4d0ad68be25c0d812b))
- 更新 .github/sync-to-gitee.sh ([`256d45e`](https://gitee.com/jermaine/yate/commit/256d45e48e20eae847585578d391c38b796270ef))
- 更新 .github/sync-to-gitee.sh ([`7986aa9`](https://gitee.com/jermaine/yate/commit/7986aa9208971a02adb1e948e90c681df905344e))

### 其他变更

- 回退「登记第三轮评审发现（双语 TOCTOU）」 ([`3b4b889`](https://gitee.com/jermaine/yate/commit/3b4b8890046cf6dfe91d81a266ab0d0bfc82fb8b))
- 从 WindowFlows 移除无用的 explorer_tree 参数 ([`2632a19`](https://gitee.com/jermaine/yate/commit/2632a19c700366912f96ea46daf604bf1a6bde3a))
- 覆盖层注入屏幕栈动词与 current_screen 查询 ([`6f6baee`](https://gitee.com/jermaine/yate/commit/6f6baee46d07cce96435026bf3c4dffaf80174a3))
- 窗格流程注入 spawn 动词与 explorer_focused 查询 ([`2ebcdf4`](https://gitee.com/jermaine/yate/commit/2ebcdf4a4e68e884d9aa6913fc2d7d3ef2cdf12c))
- 补全流程注入 spawn 动词与 has_modal_screen 查询 ([`6b03fca`](https://gitee.com/jermaine/yate/commit/6b03fca88d65ddaae774191e79c9c782b52b6dac))
- LSP 同步注入 spawn 动词并复用 overlays.push ([`51a5af2`](https://gitee.com/jermaine/yate/commit/51a5af27d878488cbcd43be6920a72e0f5eae47a))
- 外壳流程注入 run_worker 派生动词 ([`7d7b6cf`](https://gitee.com/jermaine/yate/commit/7d7b6cfdcad7a681149d0adcca5ec28541ab4e51))
- 文档流程注入 run_worker 派生动词 ([`ae2c6ec`](https://gitee.com/jermaine/yate/commit/ae2c6ec7d5e1d0fe6e4aecec5d731d55b4545ea0))
- 编辑器注入点注解精确为 App[None] ([`993c9c3`](https://gitee.com/jermaine/yate/commit/993c9c38b3e6235809da3a6dc5e779e6387f802e))

## [0.2.6] - 2026-09-27 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.5...v0.2.6)

### 新功能

- devtools 桥由 tracing 开关门控 ([`5d3399d`](https://gitee.com/jermaine/yate/commit/5d3399d8ad8a15a34e8f1bb8864022693c7975b9))
- 将 tracing 桥接进 devtools，新增 R12 日志规则 ([`a35a133`](https://gitee.com/jermaine/yate/commit/a35a133d36a8b24c9dfbcf876f80fc0b97653720))
- 将应用级 CSS 移入随包 app.tcss 资源 ([`3105f66`](https://gitee.com/jermaine/yate/commit/3105f66e09cba1d282d86383c6cfb21741055342))
- 在组合键驱动中解码 win32-input-mode 帧 ([`afaf000`](https://gitee.com/jermaine/yate/commit/afaf000f160021ceed5b9819643acd55cb96c026))
- 为 L0 叶子添加 trace 日志 ([`06d99a9`](https://gitee.com/jermaine/yate/commit/06d99a9a811e0122eabca176204c0b0fcfe3d413))
- 为 L1 会话与注册表添加 trace 日志 ([`4fd005f`](https://gitee.com/jermaine/yate/commit/4fd005f53829395ad2c96b640248fa10d6e0b3fa))
- 为 L2 editor_view 组件添加 trace 日志 ([`2a6e712`](https://gitee.com/jermaine/yate/commit/2a6e712f5b144ba56c2d84ecc93448294d2fc9e3))
- 为 L3 表格与补全 flow 添加 trace 日志 ([`f575211`](https://gitee.com/jermaine/yate/commit/f5752116c2bbd3c1d66b6660d26633223fe28c8b))
- 为 L4 应用外壳添加 trace 日志 ([`cc24677`](https://gitee.com/jermaine/yate/commit/cc246770784df6e9622601ba4ddb2ed17a4353ae))
- 新增带自动探测的 key_protocol 选项 ([`33f91e5`](https://gitee.com/jermaine/yate/commit/33f91e58e46be4d9621ac2d45973223406d5ebff))
- 经 Windows 控制台记录投递完整组合键 ([`ce93090`](https://gitee.com/jermaine/yate/commit/ce93090453e5630dcd02dc44628934cfa6934747))
- 新增按键组合模型与遗留编解码包 ([`5cd97d1`](https://gitee.com/jermaine/yate/commit/5cd97d1ca253f5a8e3e33a959f377aecfadb6d9b))
- 入口处记录按键事件以便终端诊断 ([`5a73fc7`](https://gitee.com/jermaine/yate/commit/5a73fc7e9747a7e2ad282218e631b73b54b5808b))
- 未映射按键事件以 debug 级记录以便诊断 ([`ff3cfc0`](https://gitee.com/jermaine/yate/commit/ff3cfc096acd62622f8b84b61e0e92ff055e8868))
- 采用 VS Code Seti 图标色板，缩进参考线淡化到 5％ ([`50c5e7c`](https://gitee.com/jermaine/yate/commit/50c5e7c1e26f7d0ec114508424aa5eaa77579abe))
- 树参考线更淡、滚动条轨道透明、文件图标着色 ([`12640b7`](https://gitee.com/jermaine/yate/commit/12640b735e120196aee74a607e78d0f28b76c4da))
- 滚动条滑块变细并以状态常量定树参考线颜色 ([`3054769`](https://gitee.com/jermaine/yate/commit/30547694e40d789be140614ef696488f815ce113))
- 安抚树光标、扁平化缩进轨、弱化滚动条 ([`b3df11a`](https://gitee.com/jermaine/yate/commit/b3df11a687a455132ee5fa387b45bd7a42d0092d))
- 打磨资源管理器图标、滚动条与分隔线 ([`b21afe7`](https://gitee.com/jermaine/yate/commit/b21afe71ce323cd66ea8f4fa65591f2642426a76))
- 新增 --readonly 启动开关与 :set readonly 选项 ([`3799aa3`](https://gitee.com/jermaine/yate/commit/3799aa3e218bbff4edf9498cb9f5a51385d2cbda))
- 缓冲区变更由只读开关守护 ([`cfd9d12`](https://gitee.com/jermaine/yate/commit/cfd9d124a051c7f212359ff86ccb178ac8c80890))
- 为发布工具新增预检守护与回滚 ([`4e6566b`](https://gitee.com/jermaine/yate/commit/4e6566bba88826b32ed68331dea4ce45ce1b88cb))

### 问题修复

- 转义消息标记并去重主题订阅者 ([`02e90fe`](https://gitee.com/jermaine/yate/commit/02e90fe9d75465473cf841acac67b43c6086aad8))
- 弥合 TerminalPanel 与 PromptBar 的遗留主题缺口 ([`0737bae`](https://gitee.com/jermaine/yate/commit/0737bae2d35b26e9bf601ef95c59a05510fc3996))
- EditorView 与 ExplorerTree 调用 super().on_mount() ([`29eeb52`](https://gitee.com/jermaine/yate/commit/29eeb52bf82a6b92ef92d2dabaff09bd24e7f011))
- 采纳 PR #28 评审建议 ([`c13f407`](https://gitee.com/jermaine/yate/commit/c13f4077937566db3d45f93fd84b529117a769ee))
- 按身份解除 devtools 桥挂接 ([`e754b27`](https://gitee.com/jermaine/yate/commit/e754b2714ac26f52adc703903b3bd82bc978f047))
- 非 Windows 跳过仅限 Windows 的 keyproto 驱动测试 ([`b9ad621`](https://gitee.com/jermaine/yate/commit/b9ad6212bf66506c356acd05b17cfe7f7224ba31))
- 容忍 win32-input-mode 帧中的空字段 ([`b21ff37`](https://gitee.com/jermaine/yate/commit/b21ff378b991f1eef360a68e479cda645485a3a9))
- 将 win32-input-mode 标志 0 视为按键抬起 ([`7b08070`](https://gitee.com/jermaine/yate/commit/7b0807073d95cd726665fa0d5fdf1c5c7fb944aa))
- 将 ctrl+2 组合键名路由到终端切换 ([`54ab508`](https://gitee.com/jermaine/yate/commit/54ab5086081611e03f54af879a7fa9e4c1c54342))
- 未知 ctrl 组合键名回退到 C0 字符 ([`1db6175`](https://gitee.com/jermaine/yate/commit/1db6175d0e62891df95adda23e15c00ffa1f910c))
- 接受 ctrl+/ 作为 0x1f 切换字节的别名 ([`1d1f3d8`](https://gitee.com/jermaine/yate/commit/1d1f3d852a1415c489cf34026b41c734d149e596))
- 将 ctrl+_ 映射到 0x1f 使 ctrl+/ 在旧终端可用 ([`b03e40f`](https://gitee.com/jermaine/yate/commit/b03e40f16d255bc75559002e345958933ce1aa32))
- 缩进参考线调暗到低于侧栏标题的弱化灰 ([`0221ffa`](https://gitee.com/jermaine/yate/commit/0221ffa629ba7930e939253940ec4727a3356833))
- 恢复树横向滚动条、新增末子节点终止符、固化参考线颜色 ([`196d9e0`](https://gitee.com/jermaine/yate/commit/196d9e005b8b529772158ad37c836442c8788691))
- 缩进轨对齐父图标下方，移除树横向滚动条 ([`fbcab99`](https://gitee.com/jermaine/yate/commit/fbcab9994f0505597aa0f19bd536d368a1836da9))
- 处理 PR 24 对只读功能的评审 ([`1f82fae`](https://gitee.com/jermaine/yate/commit/1f82fae3020351849b334644b8caec2f7cee629f))
- 弥合只读功能的评审缺口 ([`8b6b1b4`](https://gitee.com/jermaine/yate/commit/8b6b1b4598ef30054307c1c5f9c6e0c18d04e9dc))
- 将 tree-sitter 依赖纳入 dev extra ([`f57db3c`](https://gitee.com/jermaine/yate/commit/f57db3c7146524128318e4f933df76d3422649d5))

### 重构

- 收紧提示符状态机并解耦卸载测试 ([`d1dbb79`](https://gitee.com/jermaine/yate/commit/d1dbb79bafb3b971d360e6280da5302163cc7dbf))
- 组件自有主题绘制与滚动条注入 ([`046fcff`](https://gitee.com/jermaine/yate/commit/046fcffe1129c0e42eeb5ea855ea6caca668536f))
- 将 devtools 桥挂载到应用生命周期 ([`036bd2a`](https://gitee.com/jermaine/yate/commit/036bd2acadb3a5800122b366a5c3c378fd41f4d7))
- 经 tracing 记录监控崩溃，移除 App 导入 ([`003263e`](https://gitee.com/jermaine/yate/commit/003263efaf958ad066e3bad69c9968b8b7cc0f78))
- 评审后打磨 tcss 加载器 ([`7e51d6b`](https://gitee.com/jermaine/yate/commit/7e51d6bec52ba534f61d92cd671146a067342d37))
- 移除失效原始字节表并守护叶子包 ([`f10002e`](https://gitee.com/jermaine/yate/commit/f10002e0f37d129d423984194a68b6ecb1915f61))
- 去重 icons 中的扩展名解析 ([`df631e6`](https://gitee.com/jermaine/yate/commit/df631e6dffe8651fe96bc7e74e24b35bcdd6460d))
- 将 yaterc 加载器与 editor_view.theme 解耦 ([`bd1c2cf`](https://gitee.com/jermaine/yate/commit/bd1c2cf7a1ed3a761df94a6c172b599a9809e503))

### 文档

- 将 R13 组件自有主题与扩展分层落为条文 ([`9216480`](https://gitee.com/jermaine/yate/commit/92164801d941eee9172cf13a2f1fd50a5e547c2b))
- 新增 plan-before-execute 工作流规则 ([`717fe08`](https://gitee.com/jermaine/yate/commit/717fe08a09ec192886ad40db70b8d6991ee2f1ee))
- 将 theme-ownership 计划重组为 README 与 A-E 分册 ([`fec98ed`](https://gitee.com/jermaine/yate/commit/fec98ed60866d906e9a93d78c6f382c561c0faf5))
- 将 theme-ownership 拆分为子计划并补齐冒烟缺口 ([`766b266`](https://gitee.com/jermaine/yate/commit/766b266b2757a042037f7a1ddf19937c118db39a))
- 回填 theme-ownership 治理结果 ([`47567db`](https://gitee.com/jermaine/yate/commit/47567db411560fc6d7424fae618dd3548fab5304))
- 登记含架构张力的 ui-refine 评审 ([`7c2ea3e`](https://gitee.com/jermaine/yate/commit/7c2ea3e6cebe2f1a7daad520f6bd4b9989fab5d1))
- 修正 PR #28 登记中的修复提交哈希 ([`392d038`](https://gitee.com/jermaine/yate/commit/392d0381dde8c8e5206913a28eefcc3ffc9ffe54))
- 登记 logging 分支评审轮次 ([`81b9525`](https://gitee.com/jermaine/yate/commit/81b952591c9d103cbc4e60c7244befce015a1d46))
- 修复守护 docstring 中过期的桥挂载点 ([`44972c9`](https://gitee.com/jermaine/yate/commit/44972c9b8de7aeb5b1135de4c4d240ca663dc05b))
- 以 devtools 桥设计扩充 R12 ([`b7a30f9`](https://gitee.com/jermaine/yate/commit/b7a30f97238a0c8282b499f1bc912ea8e0186371))
- 新增 tcss 实现评审报告 ([`25e111c`](https://gitee.com/jermaine/yate/commit/25e111c2970ecac7c0ff6b27d7781df6eb7f96f6))
- 为问题 IKINFT 新增 tcss 拆分计划 ([`b8d9e59`](https://gitee.com/jermaine/yate/commit/b8d9e5988adf347693d562fe1d1a1d47d3ac883f))
- 将 Gitee PR #26 AI 评审登记进 review.md ([`89956da`](https://gitee.com/jermaine/yate/commit/89956da0ac03797688c6a9bc22870cbc1ba88ade))
- 登记键位分支评审报告 ([`7a6cbe8`](https://gitee.com/jermaine/yate/commit/7a6cbe8d9d1d64b31bad5568a2811b151c3e4e1f))
- 在计划状态中记录 PB6 真实输入验证 ([`24266a6`](https://gitee.com/jermaine/yate/commit/24266a638d1ecf984ca07021cf1881214332390a))
- 将校准结果回填进日志计划 ([`3e8329a`](https://gitee.com/jermaine/yate/commit/3e8329a36746f6394e62dc00bfde6cd0373812b8))
- 为问题 IKIN1Z 起草分层日志计划 ([`970de77`](https://gitee.com/jermaine/yate/commit/970de7796fd50c780f9fccd56487d45adadd5ca9))
- 在 Phase B 状态中记录 NUL 组合键命名轮次 ([`b246fa5`](https://gitee.com/jermaine/yate/commit/b246fa557d3a36ea1ed890848d56e601069e7fd8))
- 文档说明 key_protocol 与 windows 组合键可用性 ([`c9713df`](https://gitee.com/jermaine/yate/commit/c9713df993b7926eb55fdd38cdd736d54dd3e3d1))
- 开启 Phase B 执行 ([`816f60d`](https://gitee.com/jermaine/yate/commit/816f60d99c8b591ade6615d1690802c0f57cad96))
- 在 Phase B 范围记录 ctrl+` 与 NUL 冲突 ([`8eb49f3`](https://gitee.com/jermaine/yate/commit/8eb49f3c68163d5189aed9ee2644e31828a87a3a))
- 以实测 trace 结论关闭 Phase A ([`91daf6c`](https://gitee.com/jermaine/yate/commit/91daf6c0b835c86e8aa9571612fdc783ebd3c087))
- 在 v3 状态记录 trace 结论与 PA2b 回退 ([`d56e43a`](https://gitee.com/jermaine/yate/commit/d56e43ad31ce100d42836533a11523506d8bd2f6))
- 记录探针发现与 v3 计划 ([`beea5e0`](https://gitee.com/jermaine/yate/commit/beea5e07bdaf68856bf1a73d4bc1b8bea8174e8d))
- 按 key 界定 Phase A/B，并给出 vim 吞键根因 ([`c2405a2`](https://gitee.com/jermaine/yate/commit/c2405a2f4c369ccf8db9f1735a35b78aeb39c91e))
- 部分实测结果后重规划为 Phase A 可达性修复 ([`218765f`](https://gitee.com/jermaine/yate/commit/218765fefa0886963003d76f85a6493d72cc92d3))
- 标记 SP5 门禁完成、矩阵待验证 ([`333c95d`](https://gitee.com/jermaine/yate/commit/333c95da427b8032231345da68a6d26618c343b8))
- 在 keybinding-fix 子计划记录门禁结果 ([`85d5e77`](https://gitee.com/jermaine/yate/commit/85d5e77ed8488947a9e5049daf3306bf56bc9568))
- 将 IKH1RA 处置回填到评审与 P2 计划 ([`ebee085`](https://gitee.com/jermaine/yate/commit/ebee085f05ceea43ce15ecb9b9ca4d854d78c678))
- 注明 ctrl+数字键位的终端兼容性 ([`f26e65d`](https://gitee.com/jermaine/yate/commit/f26e65d9724b8c7f88713bf9fd2d7ed51324357f))
- 恢复并校准 Windows Terminal 键位计划 ([`a9174fc`](https://gitee.com/jermaine/yate/commit/a9174fc66fd1c73f8eccc3ca031515eaed23e483))
- 为问题 IKINF3 新增 UI 打磨设计计划 ([`a6f336f`](https://gitee.com/jermaine/yate/commit/a6f336f0c253df25c75443add715f4271abf61c0))
- 登记 Gitee PR 24 评审结论元数据 ([`98eebb7`](https://gitee.com/jermaine/yate/commit/98eebb72e1e8602c1756a95f6f34e0abbd7c2b16))
- 在评审列表记录只读评审轮次 ([`635f50e`](https://gitee.com/jermaine/yate/commit/635f50eaf84b95c5d81c9ba2efbd8fb0719b5f50))
- 在计划文档记录只读评审轮次 ([`e7e6fed`](https://gitee.com/jermaine/yate/commit/e7e6fed17209b70ae66052403e74573ed85d5fd5))
- 统一手册与扩展说明中的只读措辞 ([`d960a08`](https://gitee.com/jermaine/yate/commit/d960a08c437136fa82e32e439262916c6f2cbc0c))
- 回填主题重构执行记录 ([`d6868bf`](https://gitee.com/jermaine/yate/commit/d6868bfc877f69fd8c22f1d3da7280a3e6f9557e))
- 强制配置层无 UI 并记录 N30 决策 ([`066ae12`](https://gitee.com/jermaine/yate/commit/066ae124571b1fda0d5e77114cda54dd0465b770))
- 新增主题层重构计划集（N30） ([`7370918`](https://gitee.com/jermaine/yate/commit/737091845c2a6b59a6107bc3d8d1afa7fade1811))
- 在手册与扩展说明中文档化 readonly 选项 ([`ed4f924`](https://gitee.com/jermaine/yate/commit/ed4f9246b75619ffd531f488d8b1e06c5bcfbd1e))
- 新增 2026-09-26 全量项目评审报告 ([`44f2f53`](https://gitee.com/jermaine/yate/commit/44f2f5385b4123aca748906a7371f498a5bce8de))
- 以正确区段重新生成双语变更日志 ([`faa6d75`](https://gitee.com/jermaine/yate/commit/faa6d754bc734b267665ff237b36e3d1fcbb53d7))
- 回填加固结果与验证清单 ([`2ba8f69`](https://gitee.com/jermaine/yate/commit/2ba8f699c46b2d72e88f26a98e013812958086d9))
- 新增发布工具加固计划 ([`aecf3e3`](https://gitee.com/jermaine/yate/commit/aecf3e3151ef6ca10cead29d4b70ec3053bca02b))
- 翻译 3.12 迁移与发布条目 ([`b599685`](https://gitee.com/jermaine/yate/commit/b5996857babbfad56b5a70e2e1e3768bbcec3bce))

### 测试

- 守护逐组件滚动条注入与主题归属 ([`1b49208`](https://gitee.com/jermaine/yate/commit/1b49208b6bb3738d9b31783fda5f821634ca6837))
- 从桥生命周期守护中移除多余的 win32 跳过 ([`905385f`](https://gitee.com/jermaine/yate/commit/905385fce642009654b2a3197695b4ea1d8c9052))
- 覆盖 saveas 命令，补上命令覆盖缺口 ([`91abd8d`](https://gitee.com/jermaine/yate/commit/91abd8dec70c49abd34a2b23453abe82ff042c5a))
- 为组合键驱动新增无人值守真实输入测试架 ([`fe4d92c`](https://gitee.com/jermaine/yate/commit/fe4d92ce5c8a729e4b28c6053ea0a07811030f48))
- 守护惰性日志格式化 ([`89c1319`](https://gitee.com/jermaine/yate/commit/89c1319ad23966b1d63448bc35fbb28ff6445914))
- 固化全局组合键在 vim 模式下的可达性 ([`34ab059`](https://gitee.com/jermaine/yate/commit/34ab0594a36e1c02a97880b46e2c6df304d2077c))
- 用试点守护固化全局组合键分发分支 ([`678c02c`](https://gitee.com/jermaine/yate/commit/678c02cd163df7b9b15646932c5308ed585e6466))
- 覆盖会话级只读、saveas 与保存守护 ([`dd47be0`](https://gitee.com/jermaine/yate/commit/dd47be0ed9dd33062320f12e9921a89325b87343))
- 覆盖只读缓冲区、命令与启动 flow ([`944c0a5`](https://gitee.com/jermaine/yate/commit/944c0a5e6f18b676e6e36fd43f9edc739a3f1bb4))

### 构建与工程

- 新增 SP5 手动矩阵验证脚本 ([`3a8a29b`](https://gitee.com/jermaine/yate/commit/3a8a29ba6beec7263a425ae95d67592b315c392b))
- 新增 agents 链接 ([`479f192`](https://gitee.com/jermaine/yate/commit/479f1923a641c3388cc6c3cef3a4febb34ca9f45))

## [0.2.5] - 2026-09-26 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.4...v0.2.5)

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

- 版本 bump 正则加 re.MULTILINE 锚定 ([`5b8c508`](https://gitee.com/jermaine/yate/commit/5b8c50886e062d4d41990b4a1c34d52aeebafff8))
  - 包 __init__ 以模块 docstring 开头，无 MULTILINE 的 ^ 锚点永远匹配不到 __version__ 行
- 发布工具只更新单一动态版本源 ([`0db2aab`](https://gitee.com/jermaine/yate/commit/0db2aab2392ebfeb6d3a77604b9ff82bc9ac1fb6))
  - test_theme_palettes 的静态版本断言已在 P2 清理中移除，删除失效的第二 bump 目标
- 修复 editor_view 向 run_worker 传递即时协程的问题 ([`ba5946b`](https://gitee.com/jermaine/yate/commit/ba5946b7d20a58b9b4c5b8982198840213719762))
  - 改为传协程函数由 worker 自行构建，避免协程未被消费的告警
- ctrl+q 改走注册的退出动作 ([`b9e73be`](https://gitee.com/jermaine/yate/commit/b9e73be2c8a713490e28283bd5b65cba44f35314))
- 落地 P2 第一波清理与守卫（core/syntax/term/tools） ([`2dad4fc`](https://gitee.com/jermaine/yate/commit/2dad4fcd606c4b394985ddfd7d7ff731596b68ee))
- 更新 .github/sync-to-gitee.sh 同步脚本 ([`0597289`](https://gitee.com/jermaine/yate/commit/05972894ca4dd1744be4ac440ae709d642b39a5b))
- 滚动恢复进行中时拦截滚动捕获 ([`1a02177`](https://gitee.com/jermaine/yate/commit/1a021773c756217bea4ec4fe9cace7102e2b6b2f))
  - 防止恢复期间捕获到中间态滚动位置
- 挂载期滚动恢复失败重试并加固捕获守卫 ([`73110ab`](https://gitee.com/jermaine/yate/commit/73110abc034be6a1e1e562feff2ce043dabf2418))
- 呈现 :trust 拒绝原因并补文档化 spawn 清理 ([`3c53fa4`](https://gitee.com/jermaine/yate/commit/3c53fa411eba15e831e2e42fda9fb7280aaf17aa))
- logs/services/document 健壮性修复与 S39 最小加固 ([`42d9b12`](https://gitee.com/jermaine/yate/commit/42d9b12f9527af5f9afb2de8fe21cfc6478ef7ca))
- 修复终端、补全与 vim 路径的多处正确性问题 ([`66fb5ba`](https://gitee.com/jermaine/yate/commit/66fb5ba7c4aa02f58c2b8dcd44685f778fb32660))
- 削减逐帧渲染开销并加固工具链 ([`d7e422c`](https://gitee.com/jermaine/yate/commit/d7e422caded6e287b65e2049f4ef7ccaf18f021c))
- 发布工具自动探测默认发布分支并透传 --overrides ([`322881c`](https://gitee.com/jermaine/yate/commit/322881c2c8f4b50942d3d33d070a00d5c25b7fae))
- LSP 启动槽仅在自身任务持有时弹出 ([`dc1f3ac`](https://gitee.com/jermaine/yate/commit/dc1f3ac3e32fd4f9b891c2f79237fdaa3f4b2063))
- 读循环崩溃时让 LSP 客户端失败而非挂起请求 ([`e5a3001`](https://gitee.com/jermaine/yate/commit/e5a30018de9110ad23d3b17412f5f0547276ad21))
- Gitee SSH 横幅检测免疫不可见字符 ([`05ead06`](https://gitee.com/jermaine/yate/commit/05ead06d51b0d7e2f90f49a67976cfc2f7a81f6f))
  - 横幅含 NBSP/零宽字符导致子串匹配误判失败；改为仅保留字母数字后匹配 successfullyauthenticated，并始终打印横幅
- version_lines 下沉 cli.py，统一 vim F 键无效动作处理 ([`44b67ea`](https://gitee.com/jermaine/yate/commit/44b67eabb7e61e282be2011522e7445734fc2201))
- 处置 2026-09-24 代码审查发现 ([`cf889b5`](https://gitee.com/jermaine/yate/commit/cf889b513624b1c45f8f0b4923a1c88c43c3220e))
- 修复 PR #13 审查问题：原子保存保留权限、信任路径统一 resolve、未知 action 不再吞键等 ([`33584e6`](https://gitee.com/jermaine/yate/commit/33584e640a443b96b90e950eb99e8f1805d5ce3b))
  - 含 2 个阻断项 + 4 个改进项与配套测试守卫；详见 .trae/reviews/2026-09-24-pr13-review.md 的 PR #13 章节
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

- 以 typing.override 标注基类覆写 ([`7a2cf79`](https://gitee.com/jermaine/yate/commit/7a2cf7910337fe4df3448c6c9f9cbb1d667fdf3b))
  - 32 处覆写方法加 @override，reportImplicitOverride=error 写入 pyright 配置防回归
- 全仓采用 PEP 604 联合类型 ([`866bb45`](https://gitee.com/jermaine/yate/commit/866bb45b434f537507515efc94e9b7002c50d44c))
  - pyupgrade 迁移 313 处 Optional/Union（53 文件），X | None 全面替代并归零旧写法
- 落地 P2 第二波清理与守卫（editor/keymaps/services） ([`a6e6f4e`](https://gitee.com/jermaine/yate/commit/a6e6f4e73db051a886a4fe05f7ee8aa3b48691ee))
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

- 翻译 v0.2.5 发布条目 ([`46e42c3`](https://gitee.com/jermaine/yate/commit/46e42c3a12563a3519741032bc6332f076c2c98f))
  - 为进入 0.2.5 段的三条发布流程提交补齐中文摘要
- 补齐缺失的中文翻译并刷新变更日志 ([`c7fa15a`](https://gitee.com/jermaine/yate/commit/c7fa15aad14c42dda1483e0b6421d5e0113848aa))
  - 为 42 条缺译条目补齐中文摘要，翻译覆盖率达 254/254
- 登记 Python 3.12 迁移审查记录 ([`6c394d9`](https://gitee.com/jermaine/yate/commit/6c394d995607536f900e85c1547e7d004373e973))
  - 双校验代理复核加 6 处高危覆写抽查，两项 minor（导入残留已修、Gitee 3.12 镜像待观察）
- 回填 3.12 升级执行记录 ([`b0c022d`](https://gitee.com/jermaine/yate/commit/b0c022dbc319ad35854b217b2f7d9d2789563ce1))
  - 校准记录留痕基线数字、D1 拍板与 pyupgrade 偏离项
- 3.12 升级方案拆分为按波任务文件 ([`5d9cb59`](https://gitee.com/jermaine/yate/commit/5d9cb596370d3e346f2bc562422dc2663c13a69d))
  - 总纲 README 加 plan_SP0-SP4 五份子计划，每份含独占文件清单与验证命令
- 登记 2026-09-25 审查分诊结果 ([`dfce21e`](https://gitee.com/jermaine/yate/commit/dfce21e1a2b7ac8f7323988b197f7788594b6716))
  - EOL 误报归档，HighlightProbe 类型收紧登记待修
- 新增 Python 3.12 升级方案 ([`104a617`](https://gitee.com/jermaine/yate/commit/104a617ef53fa98b70b0e3aedf2cca2c1dd529da))
  - 核心动机为运行时性能收益（3.11 约 1.25 倍提速），波次拆分 SP0-SP4 四提交
- 编码规范 3.12 化：PEP 604 翻转与 PEP 695 指引 ([`4fe388c`](https://gitee.com/jermaine/yate/commit/4fe388cd0863a178552bb55e24e2a3da9799540c))
  - 可空标注改用 X | None，泛型首选 PEP 695 语法，新增 typing.Self 与 @override 检查项
- 修正 yaterc 方案文档文件名笔误（pywright→pyright） ([`11bab59`](https://gitee.com/jermaine/yate/commit/11bab597c95329329ece2e09766e26a80517d51b))
- 四份 remove_type_checking 文档合并为单篇 ADR ([`f9b4d0b`](https://gitee.com/jermaine/yate/commit/f9b4d0b626380be862385b78ba76930156f8f774))
- 回填 wave-1 子计划校准记录 ([`8c30871`](https://gitee.com/jermaine/yate/commit/8c308715a0eb4e25d4e633966d746a1d982d3ec0))
- P2 改进计划拆分为按波并行的子计划 ([`ea13961`](https://gitee.com/jermaine/yate/commit/ea13961a45953f109de7990c8c4ff7fbb510f0a3))
- 新增架构总览与 Textual 框架挂点笔记（wiki） ([`f2dad15`](https://gitee.com/jermaine/yate/commit/f2dad159a6f06d6cadf9ef2dffda20364a6f141b))
- 回填 P1 波次结果并登记 gitdata 缺口 ([`6489396`](https://gitee.com/jermaine/yate/commit/6489396a4bf888d17fafed0cb420219e961b209e))
- P1 建议计划拆分为 7 份文件独占子计划 ([`7e1372f`](https://gitee.com/jermaine/yate/commit/7e1372f27969c5d3ff19c0d408e429d5ed0dcf31))
- 批次大小上限规则对齐 6 代理并发上限 ([`3ea5911`](https://gitee.com/jermaine/yate/commit/3ea5911d1f4dc4ccb08619e4d4218286cb94f75b))
- 子代理并发上限由 5 提到 6 ([`994702a`](https://gitee.com/jermaine/yate/commit/994702a6605cffee83e4ebda8650a4bb036c133b))
- 审查发现与修复计划同步至代码现状 ([`8133417`](https://gitee.com/jermaine/yate/commit/8133417a59e79528093763a533b54eeb9fce4c56))
- review.md 登记 logs.py 两项审查发现 ([`498fc9b`](https://gitee.com/jermaine/yate/commit/498fc9be63b92bc20bb34df71fb08df5eff8e2f7))
- 2026-09-24 审查状态并入 review.md ([`733c01b`](https://gitee.com/jermaine/yate/commit/733c01b93fc227d1459f1b364041942834760041))
- 登记 2026-09-24 分支审查报告 ([`aba991e`](https://gitee.com/jermaine/yate/commit/aba991e3121d6e262326e158a753c203aeec7115))
- 变更日志补译 PR #13 修复条目 ([`c2e18b8`](https://gitee.com/jermaine/yate/commit/c2e18b885d4fc224ec8d3a45af05116ae9c0f707))
- 全量核对测试 mock 目标，确认重构后无静默失效 ([`406fcd8`](https://gitee.com/jermaine/yate/commit/406fcd85df4bfb354cd173cbc1dbd0bf7e68f362))
- 登记 Esc 关闭弹窗后被在途 worker 重开的竞态（仅登记未修） ([`60ea88e`](https://gitee.com/jermaine/yate/commit/60ea88eb66e51f94c88cde8eab1b24cc25781152))
- 补齐维护类提交的中文翻译并刷新变更日志 ([`217a93f`](https://gitee.com/jermaine/yate/commit/217a93f98e09413d35882f4f0852e646ee3f3b8f))
- 刷新双语变更日志以记录归因修正 ([`e8d4dd4`](https://gitee.com/jermaine/yate/commit/e8d4dd4cad18e771a96f5d7ffdd6b333eb8ee754))
- 修正补全弹窗吞键问题的归因记录 ([`fd697bb`](https://gitee.com/jermaine/yate/commit/fd697bb3c04c6b4e72dd310b128e2047b5487e6e))
  - master 实测未受影响：当时未识别键会冒泡到 YateApp.on_key；本轮分层重构取消冒泡后才显现
- 变更日志保持修复条目已翻译 ([`7180d5f`](https://gitee.com/jermaine/yate/commit/7180d5f11d5dadc32a614931728ea0a0e604dcce))
- 变更日志记录补全弹窗按键放行修复 ([`5a1afbd`](https://gitee.com/jermaine/yate/commit/5a1afbdc862cbccdfc24fd2d90c6f9a162cdd52e))
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

- 键位测试独立成模块：actions、notation 与 KeymapSet ([`3182414`](https://gitee.com/jermaine/yate/commit/3182414903e971c65e1c2dff8b7e11bcf2d5ad99))
- 手册测试改为加载完成后才断言内容 ([`331e281`](https://gitee.com/jermaine/yate/commit/331e281dc9ddfe070a82f7261d9c84b0ab320932))
- S40 合并测试改为断言防抖窗口已布防 ([`53a6e93`](https://gitee.com/jermaine/yate/commit/53a6e934dd2709ddd6af07fe457a40b06bdb0643))
- S40 防抖测试脱离真实时间依赖 ([`2f7a7ad`](https://gitee.com/jermaine/yate/commit/2f7a7adfe09f787cce26374173e0269ab28dc6ac))
- 修复 workspace 与 manual 两腿 CI 的失败用例 ([`8a5d1bf`](https://gitee.com/jermaine/yate/commit/8a5d1bfb2fdd8503d6f567bdc41ebda0d5c11f55))
- 收尾 P2 跟进项并加固偶发 pilot 测试 ([`ae220fb`](https://gitee.com/jermaine/yate/commit/ae220fb7f9bf5cacfea24be8a0eb1ef9cad2a7d2))
- 为 SP3 渲染路径修复补齐专用守卫测试 ([`d0b7a9e`](https://gitee.com/jermaine/yate/commit/d0b7a9e5749829daa0aa5b1d3f512b895dcf4cf6))
- 冒烟新增补全弹窗键位分工回归场景 ([`ef63f07`](https://gitee.com/jermaine/yate/commit/ef63f073aa074d9e21a66a40d4c92ca72bd8153d))
  - 字符与全局键（ctrl+z）fall-through，tab/down/esc 仍归弹窗；等待防抖落地避免竞态
- 冒烟测试覆盖全部已注册命令与动作 ([`0984361`](https://gitee.com/jermaine/yate/commit/09843611fdf12a69273e561750db7a75109eb65d))
  - 新增 19 个场景（65→86），命令与动作覆盖达到 43/43、65/65，未改动产品代码
- 补全测试覆盖弹窗几何与缓冲区补全源 ([`f01b713`](https://gitee.com/jermaine/yate/commit/f01b713dd490a2303decc730e21784da1a3dbaef))
- 字体测试覆盖注册表扫描、检测、安装与设置改写 ([`a6dcbef`](https://gitee.com/jermaine/yate/commit/a6dcbef8f2822d45b59cc0d52e975eedfbc3300b))
- PTY 测试覆盖各平台后端与门面失败路径 ([`64e2dd4`](https://gitee.com/jermaine/yate/commit/64e2dd48e51e9331f287770767d222c49f94326a))
- 测试与冒烟场景迁移至编辑器层 ([`61f988d`](https://gitee.com/jermaine/yate/commit/61f988d68fde73daa89cd37e7f62690026b50cd4))

### 构建与工程

- 项目 Python 下限提升至 3.12 ([`ada345b`](https://gitee.com/jermaine/yate/commit/ada345b29777dbcbf50f8de1d32c632fe2eeeeb9))
  - pyproject 与双 CI 声明面 bump；3.11 约 1.25 倍与 3.12 再 +5% 的运行时提速自此生效
- 测试套件对 RuntimeWarning 直接判失败 ([`97f9144`](https://gitee.com/jermaine/yate/commit/97f9144e540e6a1c08634651e6621c89e02728bf))
  - 经 pytest filterwarnings 把 async 忘 await 等运行时告警升级为错误
- sync-to-gitee 同步脚本补充可执行权限 ([`beecf6c`](https://gitee.com/jermaine/yate/commit/beecf6ce9977439b7ac08bc36884a70c2803ef1f))
- 新增 Gitee 同步脚本（trap 清理） ([`3ca89c4`](https://gitee.com/jermaine/yate/commit/3ca89c424efd936b2f72aaecb6665356e30e3e68))
- 新增符合仓库约定的 .editorconfig ([`c1db3a2`](https://gitee.com/jermaine/yate/commit/c1db3a2efd76c36c9ff14dc4e3a8f11ca7e53b21))
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

- 去除 future 导入后的多余空行 ([`f010056`](https://gitee.com/jermaine/yate/commit/f010056dc6758fae19e0a8e141c8bada279a1dc2))
- 冒烟工具扁平化单名字 typing 导入 ([`397ef2f`](https://gitee.com/jermaine/yate/commit/397ef2fb80a46bbdfd8caa2528e613c98df8edd5))
  - 清理 SP3 孤立导入脚本留下的括号多行残留
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
