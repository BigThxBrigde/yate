# Changelog

> Generated from the git history on 2026-09-23 · yate 0.2.4

## [Unreleased] · [compare](https://gitee.com/jermaine/yate/compare/v0.2.4...HEAD)

### Features

- gate project extensions behind workspace trust ([`a89a720`](https://gitee.com/jermaine/yate/commit/a89a720737dc808ddd2975a98855b6ae76a158dc))
- remember the desired column for vertical movement ([`b0d154d`](https://gitee.com/jermaine/yate/commit/b0d154d8972ad2e44967d3956a5e61f63d058581))
- give the executable an icon built from the yate logo ([`54cf062`](https://gitee.com/jermaine/yate/commit/54cf062e6cf451198ed03a63e30186be7f289752))
- add opt-in runtime trace logging ([`8b66b89`](https://gitee.com/jermaine/yate/commit/8b66b896d2475bde741893dbdc7a8b62154d5e2f))
- add stress scenarios and alias coverage (S + gaps) ([`4d357cc`](https://gitee.com/jermaine/yate/commit/4d357ccb78c60434848d30c6d3183834c43d36b0))
- add regression guards for past bugs (R) ([`25fdbd8`](https://gitee.com/jermaine/yate/commit/25fdbd8066c0cc3613fa3f65c2b12c547f1a0b6a))
- add integration scenarios (H) ([`f25aaba`](https://gitee.com/jermaine/yate/commit/f25aabaf3851fbc70d781b8e93259eb23b5bee7c))
- add pane, explorer and view scenarios (E/F/G) ([`5c22c8d`](https://gitee.com/jermaine/yate/commit/5c22c8dffa8062f0d12f3c1b8c506d9a441ca1e4))
- add search and file/tab scenarios (C/D) ([`0d4a2fe`](https://gitee.com/jermaine/yate/commit/0d4a2fedf03a2342563d05c417690735e6c54153))
- add editing and selection scenarios (A/B) ([`544e56d`](https://gitee.com/jermaine/yate/commit/544e56ddfe2a7f5ad334d6d960191988e54d40da))
- rebuild the harness around tagged scenarios and rich reports ([`f1787bc`](https://gitee.com/jermaine/yate/commit/f1787bc88052f03a646da88f634386a8824130a7))
- add yate ui smoke test tool ([`47dac93`](https://gitee.com/jermaine/yate/commit/47dac9311ad21b91a2aa1552716d19e1529dd3fc))

### Bug Fixes

- let non-popup keys fall through while the popup is open ([`bbeb5f6`](https://gitee.com/jermaine/yate/commit/bbeb5f6375142e1a64febf6049a4db33812c5efa))
- snapshot the command universe after the shell loads it ([`d6765c4`](https://gitee.com/jermaine/yate/commit/d6765c419394afeac842667d489c49973b699f6a))
- complete a directory once its separator is typed ([`c55f71e`](https://gitee.com/jermaine/yate/commit/c55f71e3793e80919305e3d453e6bde6b75de480))
- step over a stale registry value that cannot be deleted ([`7d0e698`](https://gitee.com/jermaine/yate/commit/7d0e698276ebeb85c15bf5eb701aa68defa123a5))
- clamp the cursor after replace_all and cover it in smoke ([`ea3a323`](https://gitee.com/jermaine/yate/commit/ea3a323c2ceca5bd5e2b603bc03e5e564ade0b95))
- keep the dirty flag exact across undo/redo ([`5190225`](https://gitee.com/jermaine/yate/commit/5190225a9173dfa4ccf86b617364b9f35b39e902))
- make saves atomic and bound undo memory ([`05106d5`](https://gitee.com/jermaine/yate/commit/05106d56d7107670aae1a8bb3ec240d21a043e74))
- settle the PTY exit future when spawn fails ([`9828b24`](https://gitee.com/jermaine/yate/commit/9828b24ba34715602d124fec7ca8335dfb8b2149))
- restore sys.excepthook and dedupe the atexit hook on uninstall ([`1c0a086`](https://gitee.com/jermaine/yate/commit/1c0a086b11d1e010b37069d2db8ab8130716374f))
- track the lazy log stream without a stub-dependent None check ([`4ded5ac`](https://gitee.com/jermaine/yate/commit/4ded5ac9d536e3aaf1be392a6538ddf5eb401d3f))
- resolve levels explicitly and create the log lazily ([`3a6f9f9`](https://gitee.com/jermaine/yate/commit/3a6f9f923a6ea456b93a26f5069284025265cebf))
- guard open_path_prompt against a None doc path ([`06b1f37`](https://gitee.com/jermaine/yate/commit/06b1f37472d9557be9f225fd9595c8055eb65e56))
- stop three state corruptions found by the new smoke suite ([`4df4e2b`](https://gitee.com/jermaine/yate/commit/4df4e2be8befc29e950c5f6f2d3b81f077036560))
- reach the command line with f5 and bind ctrl+/ in vim keymap ([`8af7457`](https://gitee.com/jermaine/yate/commit/8af745764fdb6bdae55c72478e317e1b586dc5cc))
- Fix the issue where the LSP was not notified when tabs were closed due to folder deletion ([`649f113`](https://gitee.com/jermaine/yate/commit/649f113e632a107236bd3499ba15c95c06c3c7d1))
- hand run_worker bound coroutine functions, not built coroutines ([`c020bc6`](https://gitee.com/jermaine/yate/commit/c020bc62a29a40172b29300f378e951edf9aafe5))
- don't force-quit :wq on failed save ([`68c797d`](https://gitee.com/jermaine/yate/commit/68c797d854feed6aa15684f3c2ab8768c077ef65))
- replace Get-FileHash: use native .NET SHA256 API instead to fix hash calculation failure due to PSModulePath pollution from host IDE, guarantee proper file hash generation. ([`0d06e94`](https://gitee.com/jermaine/yate/commit/0d06e947ec7e94324a978584da388fe02e21a97a))
- support F1 to F12 in vim keymap ([`91d40d8`](https://gitee.com/jermaine/yate/commit/91d40d8ed00e44f97a1ee13842d1a7e3162d6934))

### Performance

- type with one pilot call and stop sleeping 20ms per key ([`9f94d8e`](https://gitee.com/jermaine/yate/commit/9f94d8e280b625882fd8dc769e6ceaaf785c8e11))

### Refactors

- sink the pane tree model into session.py (Plan G) ([`2ee2586`](https://gitee.com/jermaine/yate/commit/2ee258656b04517c0a94030c990b27f6f13b1e9a))
- split refresh_ui into focused sub-methods and update stale docs ([`f3df035`](https://gitee.com/jermaine/yate/commit/f3df0358309173d961e7a35575118b44e90dbdef))
- drop the Feature layer for concrete editor collaborators ([`9fa5ac8`](https://gitee.com/jermaine/yate/commit/9fa5ac84b844958bd89bcc6b039dc1ed30a5897e))
- replace AppProtocol with narrow module protocols ([`738204e`](https://gitee.com/jermaine/yate/commit/738204e4e36f592e33aa1b775f21ec45634f8bde))
- drop the crash/tracing shells and import the singletons directly ([`78a2696`](https://gitee.com/jermaine/yate/commit/78a26968c091fde3d7438490de0130006e8eb351))
- unify crash diagnostics and trace logging in yate/logs.py ([`4cdf4da`](https://gitee.com/jermaine/yate/commit/4cdf4da449b36dfe42eab2939ea681a44abc4014))

### Documentation

- translate every pending entry into Chinese ([`32e5649`](https://gitee.com/jermaine/yate/commit/32e56490166bece249be93982769f7c31833521c))
- use English for every code comment and docstring ([`844cd0a`](https://gitee.com/jermaine/yate/commit/844cd0acefd38997968bc53038914bc5f6ffcba8))
- correct the quit-action finding and log the smoke-investigation issues ([`c1f83fe`](https://gitee.com/jermaine/yate/commit/c1f83fec05efbc55a125db10f2f0b36c4312a71c))
- record the scenario coverage round ([`4b0695a`](https://gitee.com/jermaine/yate/commit/4b0695ad4afcf81ff3e41773c5b741ddc40162f3))
- add the pane model sink plan into the L1 session ([`277abf9`](https://gitee.com/jermaine/yate/commit/277abf904f954e0155636076c18ae055f78cb3e5))
- record the second coverage round and the smoke coverage fix ([`c2be8dd`](https://gitee.com/jermaine/yate/commit/c2be8dd809944f673dae137ba587a52dd8bee1e0))
- guard the subagent workflow against silent member loss ([`a1c35b2`](https://gitee.com/jermaine/yate/commit/a1c35b26a86591d14cdbcce96535828a3918d47a))
- open the second coverage round for pty_proc, fonts and the popup ([`802467d`](https://gitee.com/jermaine/yate/commit/802467d6fd94ab3910310b199bc6d9bf8a1e3abc))
- record the coverage implementation and its calibrations ([`fd251e1`](https://gitee.com/jermaine/yate/commit/fd251e19a568dc8dac787aef9ed5b2e4a2371a33))
- require parallel subagents capped at five ([`942821a`](https://gitee.com/jermaine/yate/commit/942821ac6b7d85eb9cbf992c00de22bcb60ff55a))
- add code coverage and test expansion plan ([`1c0a7e0`](https://gitee.com/jermaine/yate/commit/1c0a7e0bac78a4a16ec09a90fd44d8718b3e4b1e))
- restructure review records and fix plans ([`f33c54a`](https://gitee.com/jermaine/yate/commit/f33c54ac498393521df7bf066f7498f500446f25))
- add the code-review fixes plan record ([`a270bd3`](https://gitee.com/jermaine/yate/commit/a270bd3aea7eab1be622a66bc3d17d0564bc18e1))
- close Plans E and F (plan records, rules, user docs, changelog entry) ([`6b43972`](https://gitee.com/jermaine/yate/commit/6b439727fb6f2eb664609a8f6681338cd59032a7))
- audit the layering plans against the code and tighten the guards ([`d1bfdbf`](https://gitee.com/jermaine/yate/commit/d1bfdbfd2b8c87ba91a4fc5aa06124ec90765d58))
- audit plan documents against the current code ([`4cb06a3`](https://gitee.com/jermaine/yate/commit/4cb06a361fabf691ed3d9d247cda7c51102c64af))
- add architecture boundary rules and align TYPE_CHECKING guidance ([`21db510`](https://gitee.com/jermaine/yate/commit/21db5101d244583217a8260e00cf502bdff86c9c))
- add draft plan for splitting and removing AppProtocol ([`e8f8d05`](https://gitee.com/jermaine/yate/commit/e8f8d052489176928584cb4f05feceade41bd3a0))
- rewrite the crash & tracing plans for the single-module design ([`57bcdd6`](https://gitee.com/jermaine/yate/commit/57bcdd609986ee6de6339fe782ca8b88f86f9a6d))
- rewrite the crash & tracing plans to match the implementation ([`d4919c7`](https://gitee.com/jermaine/yate/commit/d4919c75e4a6dedb8e07463ee4a4acb311cc69ac))
- update logging refactoring plan ([`35830eb`](https://gitee.com/jermaine/yate/commit/35830eb1c479e6bfc50b432d7d9c401fa0a65f05))
- add logging refactoring plan ([`35fa904`](https://gitee.com/jermaine/yate/commit/35fa904157d2bdd70f9be9c86a785dcf65eb712e))
- add python coding style ([`6e9f013`](https://gitee.com/jermaine/yate/commit/6e9f013dfe6d5993079b2985cc5aa1152b75b061))
- document the executable icon and sync the Chinese edition ([`f3e8c89`](https://gitee.com/jermaine/yate/commit/f3e8c89a1ee109aef6019bef93d88779b54583f5))
- add runtime trace logging implementation plan ([`91d1345`](https://gitee.com/jermaine/yate/commit/91d134592013a9f12099a2ccf96386e1d4686a61))
- align --help output and CLI option docs with supported flags ([`ac41c84`](https://gitee.com/jermaine/yate/commit/ac41c84f925ac25f37526a6c4f35fc9b51aed27d))
- document smoke test usage ([`9e6b487`](https://gitee.com/jermaine/yate/commit/9e6b48719f3ad8b21344afc8fa8859ea521004cd))
- document the rebuilt harness and commit the baselines ([`925ea06`](https://gitee.com/jermaine/yate/commit/925ea0630a39af7e6093d08fb061b2519ec8255e))
- add plan for fixing, extending and restyling the smoke harness ([`20227ad`](https://gitee.com/jermaine/yate/commit/20227ada961c3751482bd9c91e947227e6ea507e))
- update issue tracking and add LSP fix plan ([`61bc850`](https://gitee.com/jermaine/yate/commit/61bc8500525ad8b8bfb753182f217bafadf2ac5c))
- add completion staleness check fix plan document ([`7ddaced`](https://gitee.com/jermaine/yate/commit/7ddaced073a4a9d9102fc80f38651a9729993464))
- reorder and fix the git commit rule document ([`f677c73`](https://gitee.com/jermaine/yate/commit/f677c734ab2fa79e0cf0529badfb0db1789f6468))
- Update project issue tracking document, organize full code review issues ([`807c199`](https://gitee.com/jermaine/yate/commit/807c199c95981ed5eac850025558d42fbf1e00e8))

### Tests

- exercise every registered command and action ([`0984361`](https://gitee.com/jermaine/yate/commit/09843611fdf12a69273e561750db7a75109eb65d))
- cover the popup geometry and the buffer completion source ([`f01b713`](https://gitee.com/jermaine/yate/commit/f01b713dd490a2303decc730e21784da1a3dbaef))
- cover the registry scan, detection, install and settings rewrite ([`a6dcbef`](https://gitee.com/jermaine/yate/commit/a6dcbef8f2822d45b59cc0d52e975eedfbc3300b))
- cover the platform backends and the facade's failure paths ([`64e2dd4`](https://gitee.com/jermaine/yate/commit/64e2dd48e51e9331f287770767d222c49f94326a))
- migrate the suite and smoke scenarios to the editor layer ([`61f988d`](https://gitee.com/jermaine/yate/commit/61f988d68fde73daa89cd37e7f62690026b50cd4))

### Tooling

- ignore the local CodeBuddy workspace data ([`b2658a6`](https://gitee.com/jermaine/yate/commit/b2658a607914ed04dc9bdae52f3e39cb248dcf87))
- cover the vim keymap headlessly ([`0096123`](https://gitee.com/jermaine/yate/commit/009612391a2f85ca36e013ee8646949c31e0b839))
- cover the terminal emulator headlessly ([`fdbfa10`](https://gitee.com/jermaine/yate/commit/fdbfa10566eee8086d3a27c03ee48c65fb35417c))
- cover the workspace listing, mutation and sniffing paths ([`97b6205`](https://gitee.com/jermaine/yate/commit/97b6205509a8f303583f293bf9d609e153dca0c8))
- cover the diagnostics report edge cases ([`e449dd1`](https://gitee.com/jermaine/yate/commit/e449dd1cb72effdf7c9b04623a75b6b052b4a018))
- cover the session, registries, shell and completion modules ([`6bbe908`](https://gitee.com/jermaine/yate/commit/6bbe9082248c5c2533c8f1e629171b384e7ec951))
- add a line/branch coverage gate and broaden the core tests ([`1e15a16`](https://gitee.com/jermaine/yate/commit/1e15a1632f187de51e97a8d026960fd497e2c5a9))
- reference the theme cleanup fixture explicitly ([`719e73a`](https://gitee.com/jermaine/yate/commit/719e73a84756b87234cc9cd26d3bbb456195279d))
- keep pyright strict clean for the tracing tests ([`033c7e9`](https://gitee.com/jermaine/yate/commit/033c7e9104c26fbe63cbdaa7f4a94aec0dc22a70))
- ignore transient smoke-check json report ([`8937dc3`](https://gitee.com/jermaine/yate/commit/8937dc3d358beacdc638e42f40580ad26783108a))
- relocate baseline directory under smoke_test ([`adfbc9c`](https://gitee.com/jermaine/yate/commit/adfbc9ce6265b7851c0b914f609df1dd8f817c35))
- add vscode workspace config and update gitignore ([`c33258b`](https://gitee.com/jermaine/yate/commit/c33258b80b36213f747b4b4051a15189e8e3356e))
- add git commit specification rules file and fix command wq ([`b33706c`](https://gitee.com/jermaine/yate/commit/b33706c21979babaa5afe12edc8be10ddd62d29d))
- update yaterc_pywright_plan ([`0971a72`](https://gitee.com/jermaine/yate/commit/0971a726695f8e586c4bc2acfbe408e8a25a7efd))
- update plan ([`5ac2bb4`](https://gitee.com/jermaine/yate/commit/5ac2bb4ceb1845e6a97f140f4e48470c84cc614f))
- update plan ([`ab75198`](https://gitee.com/jermaine/yate/commit/ab75198382e8dbd8a0e00733dbfce9df969f0f18))
- update the changelog ([`03c9dee`](https://gitee.com/jermaine/yate/commit/03c9dee7d7ef81f05bc3440e2b85a1045a933ed5))
- update the changelog ([`798df3a`](https://gitee.com/jermaine/yate/commit/798df3a6a16ab03f370b5f2a707f6e08c54d2c74))
- update skill ([`54de33c`](https://gitee.com/jermaine/yate/commit/54de33c699bd11c35579472974d9d5cffe8fccc8))
- add the plan ([`53a7e09`](https://gitee.com/jermaine/yate/commit/53a7e099bf53ff8fa0be43bd2b5bba258f84709b))
- remove line break in changelog ([`cf67891`](https://gitee.com/jermaine/yate/commit/cf67891a2a9f171faac752d0fe5c53528b9ae50b))
- fix change log main repo url ([`90b71cc`](https://gitee.com/jermaine/yate/commit/90b71cc90378dee62d8c82da6f72a73797c2345e))

### Other Changes

- !4 fix(completion): Fix edge cases in completion triggering and validation logic ([`cc4b1f6`](https://gitee.com/jermaine/yate/commit/cc4b1f6ef164952d0dccaf60ab8d5c203539cd72))
- !5 refactor(editor): Refactor the split pane module to resolve type circu… ([`1325f71`](https://gitee.com/jermaine/yate/commit/1325f71edbe70046ac53384d3e988f6660a9ea4c))
- !3 fix(commands,save): improve quit handling and error coverage ([`3b4319a`](https://gitee.com/jermaine/yate/commit/3b4319a208a2c479de0c67d4d3f136743ac1f885))

## [0.2.4] - 2026-09-15 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.3...v0.2.4)

### Features

- Populate all the color scheme with prompts ([`8ae5da6`](https://gitee.com/jermaine/yate/commit/8ae5da6d5df1277b97dc56195abcea1d4107855a))

### Bug Fixes

- resolve race in test_app_textual ([`6bb2179`](https://gitee.com/jermaine/yate/commit/6bb21799d9984e30a56f4fb24604ba1da9c5ea53))
- exclude release doc commits from entries to keep gate stable ([`677f867`](https://gitee.com/jermaine/yate/commit/677f867fad1319041e5c41e4a618d42709771114))

### Tooling

- Update overlay_theme_consistency_plan ([`e3e5a37`](https://gitee.com/jermaine/yate/commit/e3e5a376f7acef8fa8e5be8c9d2b1ad136c0eada))
- Update AI docs, change into English ([`e065440`](https://gitee.com/jermaine/yate/commit/e065440e92968a594e682a5cb3c3ff6145dcc33e))
- add AI docs ([`f056703`](https://gitee.com/jermaine/yate/commit/f05670327ed749bebca277f3cb9bc35cbe42defe))
- ignore .python-version file, in case of pyenv local config ([`adae5f7`](https://gitee.com/jermaine/yate/commit/adae5f71f65f33894dfc276674c5eab8bbc8d913))

## [0.2.3] - 2026-09-15 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.2...v0.2.3)

### Bug Fixes

- Fix release tools, add version and fix versioning in source code ([`5ff9d8b`](https://gitee.com/jermaine/yate/commit/5ff9d8b8580cf5e99c433aee1413896f9cff04f7))

### Documentation

- record pytest migration in unreleased section ([`449eb30`](https://gitee.com/jermaine/yate/commit/449eb307d769586431855b488aec0dbc97e45abb))

### Tests

- migrate suite from unittest to pytest with isolated HOME ([`14e6dd3`](https://gitee.com/jermaine/yate/commit/14e6dd372dbc3ecaadc52c2080a403eb5555599f))

## [0.2.2] - 2026-09-14 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.1...v0.2.2)

### Features

- Add new tools for release, simpify the workflow ([`4fec66d`](https://gitee.com/jermaine/yate/commit/4fec66d427ef3744ff91d1b6e101799eac915c60))

### Bug Fixes

- flush pending didChange before completion and prefer interpreter-adjacent pyright ([`fa1ae55`](https://gitee.com/jermaine/yate/commit/fa1ae55aafd5b02fafe502560bf1bdc53f21e0cb))
- Fix release tools ignored issue ([`1758fff`](https://gitee.com/jermaine/yate/commit/1758fffb6543479a7c153ab9d374820641ab8147))
- debounce syntax highlighting and reuse stale tokens ([`082bc7d`](https://gitee.com/jermaine/yate/commit/082bc7d3c2824e2314b06b70ff97e5a310af0219))
- unittest test_vsplit_with_file_and_only and upgrade version ([`ceba77f`](https://gitee.com/jermaine/yate/commit/ceba77ff8e92646899e4a9c2e65af5e0359d5076))

### Tooling

- Update CHANGELOG ([`641412c`](https://gitee.com/jermaine/yate/commit/641412c7ae4701e7462b44628437382d74b0895e))
- Update READMD.zh.md ([`8566fac`](https://gitee.com/jermaine/yate/commit/8566fac589c6524486f3b4c3907f40fcd10ce851))

## [0.2.1] - 2026-09-14 · [compare](https://gitee.com/jermaine/yate/compare/v0.2.0...v0.2.1)

### Features

- add --dist artifact staging and require .venv interpreter ([`483b667`](https://gitee.com/jermaine/yate/commit/483b6679d93cc0773390887dfc38f3bc9716a620))
- Fix failed unit tests ([`5b03805`](https://gitee.com/jermaine/yate/commit/5b0380563819be1434e38f3c1dd835ca52a98695))

### Documentation

- refresh bundled changelog resources ([`107b17c`](https://gitee.com/jermaine/yate/commit/107b17c94f912002cf46802c48281930985834a0))

## [0.2.0] - 2026-09-14 · [compare](https://gitee.com/jermaine/yate/compare/v0.1.1...v0.2.0)

### Features

- add --setup-defaults/--cleanup-defaults for user config init ([`04ec16e`](https://gitee.com/jermaine/yate/commit/04ec16ea59bcc748b39ca78d1aaf3b1de9675c73))

### Documentation

- document one-command user directory setup and cleanup ([`738c2f1`](https://gitee.com/jermaine/yate/commit/738c2f1bb22b0b14aaa62a6c683a0793a93ca459))

### Tests

- cover user setup/cleanup service, flags and crash uninstall ([`6e77ebe`](https://gitee.com/jermaine/yate/commit/6e77ebed0050caf573d644218a070d7b0d7f3a8a))

## [0.1.1] - 2026-09-14 · [compare](https://gitee.com/jermaine/yate/compare/v0.1.0...v0.1.1)

### Features

- ship Dracula and Ayu theme templates ([`28d74c5`](https://gitee.com/jermaine/yate/commit/28d74c57076ee941bd400f358eeb4bec3ea9ac52))
- add One and Gruvbox built-in themes ([`a4d880b`](https://gitee.com/jermaine/yate/commit/a4d880bf2534d3e8970d2757a0631e9718148840))

### Bug Fixes

- wait for in-flight connect in stop() so spawned servers always terminate ([`7c69c6b`](https://gitee.com/jermaine/yate/commit/7c69c6bbece7a13691b76ab4786f1e7543a13c02))

### Documentation

- document eight built-in themes and template install ([`26ba949`](https://gitee.com/jermaine/yate/commit/26ba949ed4a4bce041533e2308803e52d19b3fc5))
- move changelog maintenance appendix from manuals to README ([`33190c5`](https://gitee.com/jermaine/yate/commit/33190c5a10e073ecd5c6cccefa7ecc083d859828))

### Tests

- cover palettes, templates and registry hygiene ([`a4aaa68`](https://gitee.com/jermaine/yate/commit/a4aaa68c349a4cb5c6f7bb09d9549ed26d402a1d))

### Tooling

- pin gitee origin so the changelog gate passes on GitHub ([`76518e0`](https://gitee.com/jermaine/yate/commit/76518e04a14c895507a74a854e93a9fbaa7a49ef))
- bundle tree-sitter backend and python/bash grammars in frozen builds ([`74202ac`](https://gitee.com/jermaine/yate/commit/74202accea55e7c6339eb060e3e11d4b29b22dbd))

## [0.1.0] - 2026-09-13 · [compare](https://gitee.com/jermaine/yate/compare/ROOT...v0.1.0)

_Initial release._

### Features

- generalized markdown doc screen with :changelog command and --changelog flag ([`74c8938`](https://gitee.com/jermaine/yate/commit/74c893846406fc33f173b3cf6840ebe9047186a8))
- dual-target rendering and released-section freshness gate ([`f78bc6e`](https://gitee.com/jermaine/yate/commit/f78bc6ef0e493a752098bdfad298f23bb6f10a30))
- bilingual changelog generator driven by git history ([`4144a72`](https://gitee.com/jermaine/yate/commit/4144a72e2a868a64970c0a3c12f63a516f24d80f))
- persist crash diagnostics to ~/.yate/data via faulthandler ([`4739dc3`](https://gitee.com/jermaine/yate/commit/4739dc3fd2b6d78024682458f74d1d8503901811))
- theme-aware scrollbar + clickable tab bar ([`5f4cc48`](https://gitee.com/jermaine/yate/commit/5f4cc48c14f30bf5ae5ceaa18e80f157f1c0107f))
- tree-sitter syntax backend with extension grammar registration ([`b0f95a1`](https://gitee.com/jermaine/yate/commit/b0f95a19a5a9035b8db40889bdf4cae70cd7e575))
- declarative language_servers yaterc option auto-activates ([`e1615f0`](https://gitee.com/jermaine/yate/commit/e1615f088061cd435659b0d429ff55690ec31cea))
- bare-number command jumps to line and Ctrl+G prompt ([`4ccd904`](https://gitee.com/jermaine/yate/commit/4ccd9041726904e0629fb905067fd0649b7c3fe1))
- custom syntax highlighting via extensions + C# bundle ([`db82bce`](https://gitee.com/jermaine/yate/commit/db82bcea306058ac1919a42f054f971e8301129c))
- manual syntax/filetype selection like :set filetype ([`8e9337a`](https://gitee.com/jermaine/yate/commit/8e9337a0c8f49691dcbbe3023f08e745c9a12f7b))
- bind F5 to open the ex command line ([`669f017`](https://gitee.com/jermaine/yate/commit/669f017b6c32a5731db8679fa4c31f78616845b9))
- buffer-based autocomplete and bash-style tab completion ([`bcd0426`](https://gitee.com/jermaine/yate/commit/bcd04266064ae148ab4d69e96aad5e14933cd80b))
- add --theme flag and fix --theme-dir ~ expansion ([`5e69220`](https://gitee.com/jermaine/yate/commit/5e692204956e1b809f94a99bac08732c7661ad01))
- add in-manual search ([`f002de4`](https://gitee.com/jermaine/yate/commit/f002de48dbd612275b04711ad2db5c11f82cc8a6))
- show all commands and actions, searchable by full name ([`eb4016e`](https://gitee.com/jermaine/yate/commit/eb4016efc261c4391e7cc553de4ca8a3c4b26a77))
- custom theme directories via theme_dirs and --theme-dir ([`53af6de`](https://gitee.com/jermaine/yate/commit/53af6defaff10e126c31c805904d0e2da40a1d3e))
- integrated PTY terminal panel with Ctrl+` toggle ([`ee7cd53`](https://gitee.com/jermaine/yate/commit/ee7cd5323555bb7309a2fc41405911863e4cacb3))
- language server support with autocomplete and diagnostics ([`ad28ef5`](https://gitee.com/jermaine/yate/commit/ad28ef5fb3963d6798833d4ae53d577a00c4617c))
- window switching between explorer and editor ([`8cd80b2`](https://gitee.com/jermaine/yate/commit/8cd80b26cf389d6a713fd361c079f59d138e2748))
- bilingual manual (en/zh), themed on open, table layout fix ([`a819973`](https://gitee.com/jermaine/yate/commit/a819973a7d943be31df221ae10f549f6d3f1654b))
- bundled read-only user manual viewer (F8 / :manual) ([`88d6b52`](https://gitee.com/jermaine/yate/commit/88d6b52e1ddeb789c5eb7e4776ed3d5d4e32fd1a))
- banner in ANSI Shadow figlet style ([`2cf85a1`](https://gitee.com/jermaine/yate/commit/2cf85a113005dc140697ffe1d1eaf5176d2fcf6a))
- switch command palette to alt+shift+p ([`ba6d7a6`](https://gitee.com/jermaine/yate/commit/ba6d7a6a3852132fbcc5f7d498eb896de2975c88))
- bundle JetBrains Mono Nerd Font; fix WT profile overrides ([`d2ce815`](https://gitee.com/jermaine/yate/commit/d2ce8158eba4619836b41ec067b810a752842556))

### Bug Fixes

- guard against tree-sitter 0.26 Windows heap corruption ([`85cb9ad`](https://gitee.com/jermaine/yate/commit/85cb9ad740f2a218f16c5e5c50e67a6d3612d144))
- Windows CI races — LSP child spawn during stop, 8.3 temp paths ([`3f4c4db`](https://gitee.com/jermaine/yate/commit/3f4c4dbc43144b89b6fcedf964bee7ec66758543))
- LSP didChange sync retry, extension teardown hooks, track pack specs ([`6cf4fea`](https://gitee.com/jermaine/yate/commit/6cf4fead2daea53083300332eb96751e2bc5c4f7))
- always quit on :q and hide the explorer for file launch targets ([`1a4e493`](https://gitee.com/jermaine/yate/commit/1a4e493e3685bf06f7ae4e82f5f0d3b3ffc26b24))
- close-pane command, key conflict, manual search and CJK glyphs ([`e70dd15`](https://gitee.com/jermaine/yate/commit/e70dd15505ef4e5116390d752e0154e0f1e5389a))
- dismiss the welcome page on :enew and never re-show it ([`8477ec0`](https://gitee.com/jermaine/yate/commit/8477ec06c5269088923f0958098460bfce96b2d4))
- accept the real Ctrl+grave key names so the panel closes ([`9ea2ac5`](https://gitee.com/jermaine/yate/commit/9ea2ac5fc4a02fa375797c8a42b83b4f4b9e4fd7))
- tear down background services cleanly so quitting never prints tracebacks ([`f0da8b2`](https://gitee.com/jermaine/yate/commit/f0da8b286d113d46d550c983ef88a305110983e5))
- only open ex command prompt from ":" in vim mode ([`9b76ae4`](https://gitee.com/jermaine/yate/commit/9b76ae4ccc8be426d2706577a9447fe94a9e0e9b))
- preserve early PTY output when panel lays out after spawn ([`3ca822c`](https://gitee.com/jermaine/yate/commit/3ca822c663403214336b33575d6a452683e8d1b5))
- explicit theme backgrounds; keyboard-driven file explorer ([`27b267c`](https://gitee.com/jermaine/yate/commit/27b267cbb99d135319eefaad64eba2c3e3132275))
- viewport follows cursor and buffer can scroll ([`e28de3c`](https://gitee.com/jermaine/yate/commit/e28de3c09b649cfe90ac4ed280b9168d8efbb6f6))
- Nerd Font icons, prompt echo, duplicate tab row; welcome banner ([`bf2b06a`](https://gitee.com/jermaine/yate/commit/bf2b06a99c13fa63e8fa4d84ab8c0ce11f9aa8d8))

### Performance

- keep syntax colors while moving the cursor ([`2b8b737`](https://gitee.com/jermaine/yate/commit/2b8b73748ef182dbf3921b65a51e8788331247a1))
- run blocking operations in background workers to keep the TUI responsive ([`fd48e3c`](https://gitee.com/jermaine/yate/commit/fd48e3cb6d14a20b129ab1e328f35fe1502731ed))

### Refactors

- rename controllers to app_features, explorer_files to explorer ([`94d78c0`](https://gitee.com/jermaine/yate/commit/94d78c08400d9ea022e89ec6d1df80bd1bbd1e66))
- rename app_parts to controllers, drop *_ops module names ([`e5f847b`](https://gitee.com/jermaine/yate/commit/e5f847b4d825311a5f5ba9db280e589d3d991e7a))
- extract YateApp collaborators into yate.app_parts ([`26076fd`](https://gitee.com/jermaine/yate/commit/26076fd856ee115ccb109ed084347f5cb5b27bcd))

### Documentation

- document changelog entry points in README and manuals ([`2490bb3`](https://gitee.com/jermaine/yate/commit/2490bb3301edaab5693f2e508126d184d2782faf))
- generate bilingual changelog for v0.1.0 and wire release workflow ([`fc74d5f`](https://gitee.com/jermaine/yate/commit/fc74d5f669fa103c0854357e47f5ef6d775235b4))
- sync bilingual manuals with latest features ([`8b17bf1`](https://gitee.com/jermaine/yate/commit/8b17bf1ca75add80441eecf7c38fc43f1984a3ee))
- link bilingual manual prominently at the top ([`b3b4e81`](https://gitee.com/jermaine/yate/commit/b3b4e81222b1fecefc1d8dca9af08cb5d6bff874))
- add extensions, themes and LSP configuration guides ([`bf46092`](https://gitee.com/jermaine/yate/commit/bf46092b6e99cbdc6161d4ee13ebc72c5d284a08))
- cover integrated terminal in help, welcome page and docs ([`475a650`](https://gitee.com/jermaine/yate/commit/475a650f9b2ec52ef153949c17d8dd4c4aaf9a62))

### Tests

- cover changelog gate, runtime doc views and CLI flag ([`1060811`](https://gitee.com/jermaine/yate/commit/10608119b9d848a2025f3a870cedf7455a0e68b9))
- harden rc server parsing and cover declarative LSP paths ([`3ad2a7e`](https://gitee.com/jermaine/yate/commit/3ad2a7ee9751ae3e6a588d75d737aea67649c9a3))

### Tooling

- add Chinese translations for release commits ([`6fa7663`](https://gitee.com/jermaine/yate/commit/6fa7663f9ea781576e1178778c7182f52f60bc7b))
- fetch full history for the changelog gate ([`a1d81d6`](https://gitee.com/jermaine/yate/commit/a1d81d6117f51634654361a6993d29921b8c0c1b))
- refresh bundled changelogs during packaging ([`b0ca383`](https://gitee.com/jermaine/yate/commit/b0ca3838870208978a676daa94b1e9eec5357835))
- add changelog freshness gate to both pipelines ([`1998c82`](https://gitee.com/jermaine/yate/commit/1998c82fbb4aa17972a60310bdfaa002d786925a))
- read project version dynamically from yate/__init__.py ([`7b5dd93`](https://gitee.com/jermaine/yate/commit/7b5dd93b01d8fa9dc2bb5fe77e946e57f7e2860a))
- ship docs/ in the wheel so manual links resolve after install ([`7b62b6c`](https://gitee.com/jermaine/yate/commit/7b62b6c1c5cc0520fdbbd257b161810ea3e30813))
- drop the old unrenamed manual.md ([`17a0259`](https://gitee.com/jermaine/yate/commit/17a0259c5ffade09f8937e0ec9892a27eaadd82a))

### Other Changes

- Add `yate --diag` diagnostics command and expand `--version` ([`b6d1071`](https://gitee.com/jermaine/yate/commit/b6d10711004e5d6303638151c838bbf552265c3f))
- Add vim-style split panes and explorer filtering ([`ecadd41`](https://gitee.com/jermaine/yate/commit/ecadd4162c2df393492fe316e6535d8e332355ac))
- Warn on bundled extension shadowing, drop bytecode from packages, fix Windows 8.3 rc paths ([`db93b52`](https://gitee.com/jermaine/yate/commit/db93b52af796ff953f9124a8314e881e39c35480))
- Add GitHub Actions CI with Linux and Windows matrix ([`949ed01`](https://gitee.com/jermaine/yate/commit/949ed01791e3cca2dbc1955158c8fb52978d5a32))
- Add Gitee Go pipeline running the full unittest suite ([`a2e3195`](https://gitee.com/jermaine/yate/commit/a2e3195f96b3413758dbae342618ae531e6b9d35))
- Move PyInstaller specs into pack/ and anchor paths to SPECPATH ([`f355a44`](https://gitee.com/jermaine/yate/commit/f355a44a6e1b7213570ef3b29a31671b5bae4662))
- Add cross-platform PyInstaller build scripts under pack/ ([`28a2a41`](https://gitee.com/jermaine/yate/commit/28a2a41bde57715af650a9d235768d0f42810e88))
- Clear stale status message on overlay commands and confirm silent ones ([`93845b3`](https://gitee.com/jermaine/yate/commit/93845b353cdc1477b6c406aad7e9383f002fe526))
- Add onefile PyInstaller spec producing a standalone dist/yate.exe ([`7cdd551`](https://gitee.com/jermaine/yate/commit/7cdd55149eec892586fd7dcb7c819edae0dba236))
- Sync READMEs with current implementation ([`d2c49df`](https://gitee.com/jermaine/yate/commit/d2c49dfdb8850ed0faa21484e37c0878f410483a))
- Make English the default README (README.md), Chinese becomes README.zh.md ([`3835554`](https://gitee.com/jermaine/yate/commit/3835554022e4e2b6ff0f042d3685a0f6e996620a))
- Bundle docs and extensions inside yate; add PyInstaller packaging ([`783f491`](https://gitee.com/jermaine/yate/commit/783f49116ab521840474feaa94113f48afa4be87))
- Initial commit ([`f690bf7`](https://gitee.com/jermaine/yate/commit/f690bf7d5f8be18de9b74b4006fcd50d18fda0d7))
- Initial commit: yate terminal editor ([`ef1d964`](https://gitee.com/jermaine/yate/commit/ef1d964ecc5366cd6bf4c3da943e2371608e748a))
