# 变更日志

> 本文件由 `python -m tools.changelog` 自动生成 —— 请勿手工编辑。
> 英文版：[CHANGELOG.md](CHANGELOG.md)

## [未发布] · [compare](https://gitee.com/jermaine/yate/compare/v0.2.6...HEAD)

### 新功能

- 屏保游行队支持复用繁忙行带：与走者尾部的间隙超过 `dist_upper_bound` ×
  全程即可在同一行带产生后继，同行合成多只拉开距离的精灵，结构上保证
  绝不重叠 ([`af6dbf4`](https://gitee.com/jermaine/yate/commit/af6dbf4))
- 屏保游行队节奏调优：默认产生窗口改为全程 1/8–1/3，新增
  `dist_lower_bound` / `dist_upper_bound` 键显式固定窗口（float 或
  `"p/q"` 分数，设置后忽略 `switch`） ([`30e4d4a`](https://gitee.com/jermaine/yate/commit/30e4d4ae600ee54a45962251f0a9b85a982157a7))
- 屏保改为小游行队：最新角色走到全程 25%–50%（随机）时产生后继，后继
  与所有在跑精灵名字互异、行带不相交，行满则不产生；走者按当前终端
  宽度走满全程后从右缘离场 ([`5353c9b`](https://gitee.com/jermaine/yate/commit/5353c9b575f2945161f6d510cce0771103ec014f))
- 新增全终端空闲屏保：`Alt+Shift+S` 手动开关 + 空闲自动触发，27 只角色
  shuffle 轮播（半格块像素画） ([`6766bed`](https://gitee.com/jermaine/yate/commit/6766bed55e0766c01088cb6cab929107a052db4c))
  - 灵感来自 Joel Yliluoma 的 "that_editor"（https://github.com/bisqwit/that_editor）；
    像素画均为 yate 原创致敬近似绘制，不含任何游戏素材
- 新增 yaterc `screen_saver` 字典选项（enable / interval / switch / characters） ([`5937ce4`](https://gitee.com/jermaine/yate/commit/5937ce43630f4aabcf9b839d04ae4b9f93459dcb))
- 新增 `tools.pack rosters` 子命令，生成带名字标签的阵容预览 SVG ([`c019f22`](https://gitee.com/jermaine/yate/commit/c019f2235d94746edfa2b1a93b7ae1fb192c7bf8))

### 文档

- 新增 fancy-sym 屏保方案文档集 ([`1ba5c53`](https://gitee.com/jermaine/yate/commit/1ba5c5380c5b8258158b6280340743044ff87ff2))

## [0.2.6] - 2026-09-27 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.5...v0.2.6)

### 新功能

- gate the devtools bridge on the tracing switch [缺中文] ([`5d3399d`](https://gitee.com/jermaine/yate/commit/5d3399d8ad8a15a34e8f1bb8864022693c7975b9))
- bridge tracing into devtools, add the R12 logging rule [缺中文] ([`a35a133`](https://gitee.com/jermaine/yate/commit/a35a133d36a8b24c9dfbcf876f80fc0b97653720))
- move app-level CSS to bundled app.tcss resource [缺中文] ([`3105f66`](https://gitee.com/jermaine/yate/commit/3105f66e09cba1d282d86383c6cfb21741055342))
- decode win32-input-mode frames in the chord driver [缺中文] ([`afaf000`](https://gitee.com/jermaine/yate/commit/afaf000f160021ceed5b9819643acd55cb96c026))
- add trace logs to L0 leaves [缺中文] ([`06d99a9`](https://gitee.com/jermaine/yate/commit/06d99a9a811e0122eabca176204c0b0fcfe3d413))
- add trace logs to L1 session and registries [缺中文] ([`4fd005f`](https://gitee.com/jermaine/yate/commit/4fd005f53829395ad2c96b640248fa10d6e0b3fa))
- add trace logs to L2 editor_view widgets [缺中文] ([`2a6e712`](https://gitee.com/jermaine/yate/commit/2a6e712f5b144ba56c2d84ecc93448294d2fc9e3))
- add trace logs to L3 tables and completion flow [缺中文] ([`f575211`](https://gitee.com/jermaine/yate/commit/f5752116c2bbd3c1d66b6660d26633223fe28c8b))
- add trace logs to the L4 app shell [缺中文] ([`cc24677`](https://gitee.com/jermaine/yate/commit/cc246770784df6e9622601ba4ddb2ed17a4353ae))
- add key_protocol option with auto detection [缺中文] ([`33f91e5`](https://gitee.com/jermaine/yate/commit/33f91e58e46be4d9621ac2d45973223406d5ebff))
- deliver full chords via windows console records [缺中文] ([`ce93090`](https://gitee.com/jermaine/yate/commit/ce93090453e5630dcd02dc44628934cfa6934747))
- add key chord model and legacy codec package [缺中文] ([`5cd97d1`](https://gitee.com/jermaine/yate/commit/5cd97d1ca253f5a8e3e33a959f377aecfadb6d9b))
- log key events at entry for terminal diagnostics [缺中文] ([`5a73fc7`](https://gitee.com/jermaine/yate/commit/5a73fc7e9747a7e2ad282218e631b73b54b5808b))
- log unmapped key events at debug level for diagnostics [缺中文] ([`ff3cfc0`](https://gitee.com/jermaine/yate/commit/ff3cfc096acd62622f8b84b61e0e92ff055e8868))
- adopt VS Code Seti icon palette, fade indent guides to 5% [缺中文] ([`50c5e7c`](https://gitee.com/jermaine/yate/commit/50c5e7c1e26f7d0ec114508424aa5eaa77579abe))
- fainter tree guides, transparent scrollbar tracks, tinted file icons [缺中文] ([`12640b7`](https://gitee.com/jermaine/yate/commit/12640b735e120196aee74a607e78d0f28b76c4da))
- slim scrollbar thumbs and state-constant tree guide colors [缺中文] ([`3054769`](https://gitee.com/jermaine/yate/commit/30547694e40d789be140614ef696488f815ce113))
- calm tree cursor, flatten indent rails, mute scrollbars [缺中文] ([`b3df11a`](https://gitee.com/jermaine/yate/commit/b3df11a687a455132ee5fa387b45bd7a42d0092d))
- refine explorer icons, scrollbars and dividers [缺中文] ([`b21afe7`](https://gitee.com/jermaine/yate/commit/b21afe71ce323cd66ea8f4fa65591f2642426a76))
- add --readonly startup flag and :set readonly option [缺中文] ([`3799aa3`](https://gitee.com/jermaine/yate/commit/3799aa3e218bbff4edf9498cb9f5a51385d2cbda))
- guard buffer mutations behind a read-only flag [缺中文] ([`cfd9d12`](https://gitee.com/jermaine/yate/commit/cfd9d124a051c7f212359ff86ccb178ac8c80890))
- add pre-flight guards and rollback to release tool [缺中文] ([`4e6566b`](https://gitee.com/jermaine/yate/commit/4e6566bba88826b32ed68331dea4ce45ce1b88cb))

### 问题修复

- escape message markup and dedupe theme subscribers [缺中文] ([`02e90fe`](https://gitee.com/jermaine/yate/commit/02e90fe9d75465473cf841acac67b43c6086aad8))
- close legacy theme gaps in TerminalPanel and PromptBar [缺中文] ([`0737bae`](https://gitee.com/jermaine/yate/commit/0737bae2d35b26e9bf601ef95c59a05510fc3996))
- call super().on_mount() in EditorView and ExplorerTree [缺中文] ([`29eeb52`](https://gitee.com/jermaine/yate/commit/29eeb52bf82a6b92ef92d2dabaff09bd24e7f011))
- adopt the PR #28 review suggestions [缺中文] ([`c13f407`](https://gitee.com/jermaine/yate/commit/c13f4077937566db3d45f93fd84b529117a769ee))
- detach the devtools bridge by identity [缺中文] ([`e754b27`](https://gitee.com/jermaine/yate/commit/e754b2714ac26f52adc703903b3bd82bc978f047))
- skip Windows-only keyproto driver tests on non-Windows [缺中文] ([`b9ad621`](https://gitee.com/jermaine/yate/commit/b9ad6212bf66506c356acd05b17cfe7f7224ba31))
- tolerate empty fields in win32-input-mode frames [缺中文] ([`b21ff37`](https://gitee.com/jermaine/yate/commit/b21ff378b991f1eef360a68e479cda645485a3a9))
- treat win32-input-mode flag 0 as key-up [缺中文] ([`7b08070`](https://gitee.com/jermaine/yate/commit/7b0807073d95cd726665fa0d5fdf1c5c7fb944aa))
- route ctrl+2 chord names to terminal toggle [缺中文] ([`54ab508`](https://gitee.com/jermaine/yate/commit/54ab5086081611e03f54af879a7fa9e4c1c54342))
- fall back to C0 character for unknown ctrl chord names [缺中文] ([`1db6175`](https://gitee.com/jermaine/yate/commit/1db6175d0e62891df95adda23e15c00ffa1f910c))
- accept ctrl+slash alias for the 0x1f toggle byte [缺中文] ([`1d1f3d8`](https://gitee.com/jermaine/yate/commit/1d1f3d852a1415c489cf34026b41c734d149e596))
- map ctrl+underscore to 0x1f so ctrl+/ works on legacy terminals [缺中文] ([`b03e40f`](https://gitee.com/jermaine/yate/commit/b03e40f16d255bc75559002e345958933ce1aa32))
- dim indent guides below the sidebar title's muted gray [缺中文] ([`0221ffa`](https://gitee.com/jermaine/yate/commit/0221ffa629ba7930e939253940ec4727a3356833))
- restore tree h-scrollbar, add last-child terminator, pin guide colors [缺中文] ([`196d9e0`](https://gitee.com/jermaine/yate/commit/196d9e005b8b529772158ad37c836442c8788691))
- align indent rails under parent icons, drop tree h-scrollbar [缺中文] ([`fbcab99`](https://gitee.com/jermaine/yate/commit/fbcab9994f0505597aa0f19bd536d368a1836da9))
- address PR 24 review on the readonly feature [缺中文] ([`1f82fae`](https://gitee.com/jermaine/yate/commit/1f82fae3020351849b334644b8caec2f7cee629f))
- close review gaps in the read-only feature [缺中文] ([`8b6b1b4`](https://gitee.com/jermaine/yate/commit/8b6b1b4598ef30054307c1c5f9c6e0c18d04e9dc))
- include tree-sitter deps in the dev extra [缺中文] ([`f57db3c`](https://gitee.com/jermaine/yate/commit/f57db3c7146524128318e4f933df76d3422649d5))

### 重构

- tighten prompt state machine and decouple unmount test [缺中文] ([`d1dbb79`](https://gitee.com/jermaine/yate/commit/d1dbb79bafb3b971d360e6280da5302163cc7dbf))
- widgets own theme painting and scrollbar injection [缺中文] ([`046fcff`](https://gitee.com/jermaine/yate/commit/046fcffe1129c0e42eeb5ea855ea6caca668536f))
- mount the devtools bridge on the app lifecycle [缺中文] ([`036bd2a`](https://gitee.com/jermaine/yate/commit/036bd2acadb3a5800122b366a5c3c378fd41f4d7))
- log monitor crashes via tracing, drop the App import [缺中文] ([`003263e`](https://gitee.com/jermaine/yate/commit/003263efaf958ad066e3bad69c9968b8b7cc0f78))
- polish tcss loader after review [缺中文] ([`7e51d6b`](https://gitee.com/jermaine/yate/commit/7e51d6bec52ba534f61d92cd671146a067342d37))
- drop dead raw-byte table and guard the leaf package [缺中文] ([`f10002e`](https://gitee.com/jermaine/yate/commit/f10002e0f37d129d423984194a68b6ecb1915f61))
- deduplicate file-extension parsing in icons [缺中文] ([`df631e6`](https://gitee.com/jermaine/yate/commit/df631e6dffe8651fe96bc7e74e24b35bcdd6460d))
- decouple yaterc loader from editor_view.theme [缺中文] ([`bd1c2cf`](https://gitee.com/jermaine/yate/commit/bd1c2cf7a1ed3a761df94a6c172b599a9809e503))

### 文档

- codify R13 widget-owned theming and extensions layering [缺中文] ([`9216480`](https://gitee.com/jermaine/yate/commit/92164801d941eee9172cf13a2f1fd50a5e547c2b))
- add the plan-before-execute workflow rule [缺中文] ([`717fe08`](https://gitee.com/jermaine/yate/commit/717fe08a09ec192886ad40db70b8d6991ee2f1ee))
- restructure theme-ownership plan into README + Plan A-E volumes [缺中文] ([`fec98ed`](https://gitee.com/jermaine/yate/commit/fec98ed60866d906e9a93d78c6f382c561c0faf5))
- split theme-ownership into sub-plans and close smoke gap [缺中文] ([`766b266`](https://gitee.com/jermaine/yate/commit/766b266b2757a042037f7a1ddf19937c118db39a))
- backfill theme-ownership governance results [缺中文] ([`47567db`](https://gitee.com/jermaine/yate/commit/47567db411560fc6d7424fae618dd3548fab5304))
- register the ui-refine review with architecture tensions [缺中文] ([`7c2ea3e`](https://gitee.com/jermaine/yate/commit/7c2ea3e6cebe2f1a7daad520f6bd4b9989fab5d1))
- correct the fix commit hash in the PR #28 registration [缺中文] ([`392d038`](https://gitee.com/jermaine/yate/commit/392d0381dde8c8e5206913a28eefcc3ffc9ffe54))
- register the logging-branch review round [缺中文] ([`81b9525`](https://gitee.com/jermaine/yate/commit/81b952591c9d103cbc4e60c7244befce015a1d46))
- fix stale bridge mount point in a guard docstring [缺中文] ([`44972c9`](https://gitee.com/jermaine/yate/commit/44972c9b8de7aeb5b1135de4c4d240ca663dc05b))
- expand R12 with the devtools bridge design [缺中文] ([`b7a30f9`](https://gitee.com/jermaine/yate/commit/b7a30f97238a0c8282b499f1bc912ea8e0186371))
- add tcss implementation review report [缺中文] ([`25e111c`](https://gitee.com/jermaine/yate/commit/25e111c2970ecac7c0ff6b27d7781df6eb7f96f6))
- add tcss split plan for issue IKINFT [缺中文] ([`b8d9e59`](https://gitee.com/jermaine/yate/commit/b8d9e5988adf347693d562fe1d1a1d47d3ac883f))
- register the Gitee PR #26 AI review into review.md [缺中文] ([`89956da`](https://gitee.com/jermaine/yate/commit/89956da0ac03797688c6a9bc22870cbc1ba88ade))
- register the keybinding branch review report [缺中文] ([`7a6cbe8`](https://gitee.com/jermaine/yate/commit/7a6cbe8d9d1d64b31bad5568a2811b151c3e4e1f))
- record PB6 real-input verification in plan status [缺中文] ([`24266a6`](https://gitee.com/jermaine/yate/commit/24266a638d1ecf984ca07021cf1881214332390a))
- backfill calibration results into logging plan [缺中文] ([`3e8329a`](https://gitee.com/jermaine/yate/commit/3e8329a36746f6394e62dc00bfde6cd0373812b8))
- draft layered logging plan for issue IKIN1Z [缺中文] ([`970de77`](https://gitee.com/jermaine/yate/commit/970de7796fd50c780f9fccd56487d45adadd5ca9))
- record NUL chord naming round in Phase B status [缺中文] ([`b246fa5`](https://gitee.com/jermaine/yate/commit/b246fa557d3a36ea1ed890848d56e601069e7fd8))
- document key_protocol and windows chord availability [缺中文] ([`c9713df`](https://gitee.com/jermaine/yate/commit/c9713df993b7926eb55fdd38cdd736d54dd3e3d1))
- open Phase B execution [缺中文] ([`816f60d`](https://gitee.com/jermaine/yate/commit/816f60d99c8b591ade6615d1690802c0f57cad96))
- record ctrl-grave NUL collision in Phase B scope [缺中文] ([`8eb49f3`](https://gitee.com/jermaine/yate/commit/8eb49f3c68163d5189aed9ee2644e31828a87a3a))
- close Phase A with field trace verdict [缺中文] ([`91daf6c`](https://gitee.com/jermaine/yate/commit/91daf6c0b835c86e8aa9571612fdc783ebd3c087))
- record trace verdict and PA2b fallback in v3 status [缺中文] ([`d56e43a`](https://gitee.com/jermaine/yate/commit/d56e43ad31ce100d42836533a11523506d8bd2f6))
- record probe findings and v3 plan [缺中文] ([`beea5e0`](https://gitee.com/jermaine/yate/commit/beea5e07bdaf68856bf1a73d4bc1b8bea8174e8d))
- scope phase A vs B per key with vim swallow root cause [缺中文] ([`c2405a2`](https://gitee.com/jermaine/yate/commit/c2405a2f4c369ccf8db9f1735a35b78aeb39c91e))
- replan as Phase A reachability fix after partial field result [缺中文] ([`218765f`](https://gitee.com/jermaine/yate/commit/218765fefa0886963003d76f85a6493d72cc92d3))
- mark SP5 gates done and matrix pending verification [缺中文] ([`333c95d`](https://gitee.com/jermaine/yate/commit/333c95da427b8032231345da68a6d26618c343b8))
- record gate results in keybinding-fix subplan [缺中文] ([`85d5e77`](https://gitee.com/jermaine/yate/commit/85d5e77ed8488947a9e5049daf3306bf56bc9568))
- backfill IKH1RA disposition into review and P2 plan [缺中文] ([`ebee085`](https://gitee.com/jermaine/yate/commit/ebee085f05ceea43ce15ecb9b9ca4d854d78c678))
- note terminal compatibility for ctrl+digit keybindings [缺中文] ([`f26e65d`](https://gitee.com/jermaine/yate/commit/f26e65d9724b8c7f88713bf9fd2d7ed51324357f))
- restore and calibrate Windows Terminal keybinding plans [缺中文] ([`a9174fc`](https://gitee.com/jermaine/yate/commit/a9174fc66fd1c73f8eccc3ca031515eaed23e483))
- add ui refine design plan for issue IKINF3 [缺中文] ([`a6f336f`](https://gitee.com/jermaine/yate/commit/a6f336f0c253df25c75443add715f4271abf61c0))
- register the Gitee PR 24 review verdict metadata [缺中文] ([`98eebb7`](https://gitee.com/jermaine/yate/commit/98eebb72e1e8602c1756a95f6f34e0abbd7c2b16))
- record the readonly review rounds in the review list [缺中文] ([`635f50e`](https://gitee.com/jermaine/yate/commit/635f50eaf84b95c5d81c9ba2efbd8fb0719b5f50))
- record the readonly review rounds in the plan document [缺中文] ([`e7e6fed`](https://gitee.com/jermaine/yate/commit/e7e6fed17209b70ae66052403e74573ed85d5fd5))
- align readonly wording in manual and extension notes [缺中文] ([`d960a08`](https://gitee.com/jermaine/yate/commit/d960a08c437136fa82e32e439262916c6f2cbc0c))
- backfill theme refactor execution records [缺中文] ([`d6868bf`](https://gitee.com/jermaine/yate/commit/d6868bfc877f69fd8c22f1d3da7280a3e6f9557e))
- enforce UI-free config layer and record N30 decision [缺中文] ([`066ae12`](https://gitee.com/jermaine/yate/commit/066ae124571b1fda0d5e77114cda54dd0465b770))
- add theme layer refactor plan set (N30) [缺中文] ([`7370918`](https://gitee.com/jermaine/yate/commit/737091845c2a6b59a6107bc3d8d1afa7fade1811))
- document the readonly option in manual and extension notes [缺中文] ([`ed4f924`](https://gitee.com/jermaine/yate/commit/ed4f9246b75619ffd531f488d8b1e06c5bcfbd1e))
- add 2026-09-26 full project review report [缺中文] ([`44f2f53`](https://gitee.com/jermaine/yate/commit/44f2f5385b4123aca748906a7371f498a5bce8de))
- regenerate bilingual changelogs with correct segments [缺中文] ([`faa6d75`](https://gitee.com/jermaine/yate/commit/faa6d754bc734b267665ff237b36e3d1fcbb53d7))
- backfill hardening results and verification checklist [缺中文] ([`2ba8f69`](https://gitee.com/jermaine/yate/commit/2ba8f699c46b2d72e88f26a98e013812958086d9))
- add release tool hardening plan [缺中文] ([`aecf3e3`](https://gitee.com/jermaine/yate/commit/aecf3e3151ef6ca10cead29d4b70ec3053bca02b))
- translate the 3.12 migration and release entries [缺中文] ([`b599685`](https://gitee.com/jermaine/yate/commit/b5996857babbfad56b5a70e2e1e3768bbcec3bce))

### 测试

- guard per-widget scrollbar injection and theme ownership [缺中文] ([`1b49208`](https://gitee.com/jermaine/yate/commit/1b49208b6bb3738d9b31783fda5f821634ca6837))
- drop the needless win32 skip from the bridge lifecycle guard [缺中文] ([`905385f`](https://gitee.com/jermaine/yate/commit/905385fce642009654b2a3197695b4ea1d8c9052))
- cover the saveas command, closing the command-coverage gap [缺中文] ([`91abd8d`](https://gitee.com/jermaine/yate/commit/91abd8dec70c49abd34a2b23453abe82ff042c5a))
- add unattended real-input harness for the chord driver [缺中文] ([`fe4d92c`](https://gitee.com/jermaine/yate/commit/fe4d92ce5c8a729e4b28c6053ea0a07811030f48))
- guard lazy log formatting [缺中文] ([`89c1319`](https://gitee.com/jermaine/yate/commit/89c1319ad23966b1d63448bc35fbb28ff6445914))
- pin vim-mode reachability for global chords [缺中文] ([`34ab059`](https://gitee.com/jermaine/yate/commit/34ab0594a36e1c02a97880b46e2c6df304d2077c))
- pin global chord dispatch branches with pilot guards [缺中文] ([`678c02c`](https://gitee.com/jermaine/yate/commit/678c02cd163df7b9b15646932c5308ed585e6466))
- cover session-wide readonly, saveas and the save guard [缺中文] ([`dd47be0`](https://gitee.com/jermaine/yate/commit/dd47be0ed9dd33062320f12e9921a89325b87343))
- cover the read-only buffer, command and startup flows [缺中文] ([`944c0a5`](https://gitee.com/jermaine/yate/commit/944c0a5e6f18b676e6e36fd43f9edc739a3f1bb4))

### 构建与工程

- add SP5 manual matrix verification script [缺中文] ([`3a8a29b`](https://gitee.com/jermaine/yate/commit/3a8a29ba6beec7263a425ae95d67592b315c392b))
- add agents links [缺中文] ([`479f192`](https://gitee.com/jermaine/yate/commit/479f1923a641c3388cc6c3cef3a4febb34ca9f45))

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
  - 含 2 个阻断项 + 4 个改进项与配套测试守卫；详见 .trae/issues/review.md 的 PR #13 章节
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
