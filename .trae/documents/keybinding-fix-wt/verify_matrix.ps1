# verify_matrix.ps1 — IKH1RA SP5 真机验证助手（在被测终端里运行）
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File verify_matrix.ps1
#   powershell -ExecutionPolicy Bypass -File verify_matrix.ps1 -Python <其它解释器路径>
#
# 阶段一（自动）: 逐键捕获控制台上报的字符码与修饰键 —— 直接验证根因
#   （ctrl+字母应为 0x10/0x11/0x17/0x1F 等 C0 码；ctrl+1 在 WT/conhost 下应显示
#    字符 0x31 + Control 修饰 —— 证明修饰键没有进入字符流，应用层无从恢复）
# 阶段二（交互）: 按 SP5 矩阵逐项提示，启动 yate 实测后人工确认
# 产物: 同目录 matrix_results.md（回填 SP5_gates_matrix.md 后可删除）

param(
    [string]$Python = 'd:\Programming\yate\.venv\Scripts\python.exe'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path

if (-not (Test-Path $Python)) {
    Write-Host "未找到解释器: $Python"; Read-Host '按回车退出'; exit 1
}

# ---- 终端识别 -------------------------------------------------------------
$term = 'conhost'
if ($env:WT_SESSION) { $term = 'Windows Terminal' }
elseif ($env:TERM_PROGRAM -eq 'vscode') { $term = 'VS Code terminal' }
Write-Host "检测到终端: $term"
Write-Host "仓库: $repoRoot"

# ---- 阶段一: 按键捕获 -----------------------------------------------------
Write-Host @'

========== 阶段一: 按键捕获 ==========
依次按下提示的按键（各按一次）。对照要点:
  ctrl+p/q/w  -> 字符码 0x10/0x11/0x17（C0, 正常）
  ctrl+/      -> 字符码 0x1F（C0, SP1 修复的就是它）
  ctrl+1      -> WT/conhost: 0x31('1')+Control => 修饰丢失证据;
                 kitty/WezTerm: 0x1B[49;5u 序列会拆成多次读入, Esc 开头
  Esc 结束捕获
'@
$probes = @(
    @{ name = 'ctrl+p';        hint = 'Ctrl+P' },
    @{ name = 'ctrl+q';        hint = 'Ctrl+Q' },
    @{ name = 'ctrl+w';        hint = 'Ctrl+W' },
    @{ name = 'ctrl+/';        hint = 'Ctrl+/' },
    @{ name = 'ctrl+1';        hint = 'Ctrl+1' },
    @{ name = 'ctrl+shift+e';  hint = 'Ctrl+Shift+E' },
    @{ name = 'esc(结束)';     hint = 'Esc' }
)
$capture = foreach ($p in $probes) {
    Write-Host ("请按: {0}" -f $p.hint)
    $k = [Console]::ReadKey($true)
    [pscustomobject]@{
        按键    = $p.name
        字符码  = '0x{0:X2}' -f [int][char]$k.KeyChar
        键名    = [string]$k.Key
        修饰键  = [string]$k.Modifiers
    }
    if ($k.Key -eq 'Escape') { break }
}
$capture | Format-Table -AutoSize | Out-Host

# ---- 阶段二: 应用内清单 ---------------------------------------------------
Write-Host @'

========== 阶段二: 应用内验证清单 ==========
每项会先显示操作与预期; 回车启动 yate（以仓库为工作区）, 实测退出后回来作答。
'@

$items = @(
    [pscustomobject]@{
        item   = 'ctrl+p 快速打开'
        how    = 'vsc 键位按 ctrl+p 打开面板, Esc 关闭; 按 ctrl+/ 切到 vim 再按 ctrl+p'
        expect = '两种键位下面板都打开（vim 下若未开即回归）'
    },
    [pscustomobject]@{
        item   = 'ctrl+/ 键位切换'
        how    = '反复按 ctrl+/'
        expect = 'vsc/vim 来回切换, 状态栏左下角键位/模式显示随之变化'
    },
    [pscustomobject]@{
        item   = 'ctrl+q / ctrl+w 回归'
        how    = 'vsc: ctrl+w 关闭标签, ctrl+q 触发退出守卫; vim: ctrl+w 是和弦前缀(如 ctrl+w q)'
        expect = '行为与既有版本一致, 无新增异常'
    },
    [pscustomobject]@{
        item   = 'ctrl+shift+e / ctrl+1 焦点'
        how    = '按 ctrl+shift+e, 再按 ctrl+1'
        expect = 'ctrl+shift+e 聚焦文件树; ctrl+1 见下一项的终端差异说明'
    },
    [pscustomobject]@{
        item   = 'ctrl+1 预期行为'
        how    = '按 ctrl+1'
        expect = $(if ($term -eq 'conhost' -or $term -eq 'Windows Terminal' -or $term -eq 'VS Code terminal') {
            '预期无反应（该终端丢失修饰键, 已文档化）——这一项"无反应"即通过'
        } else {
            '未识别的终端: 若为 kitty/WezTerm 应聚焦编辑器; 否则无反应即通过'
        })
    },
    [pscustomobject]@{
        item   = 'alt+shift+p 替代路径'
        how    = '按 alt+shift+p 打开命令面板'
        expect = '面板打开, 可搜索并执行命令（ctrl+1 不可达终端的替代路径）'
    }
)

$checklist = foreach ($it in $items) {
    Write-Host ("`n== {0}" -f $it.item)
    Write-Host ("   操作: {0}" -f $it.how)
    Write-Host ("   预期: {0}" -f $it.expect)
    $go = Read-Host '回车启动 yate 实测 / s 跳过启动直接作答'
    if ($go -ne 's') {
        Push-Location $repoRoot
        try { & $Python -m yate $repoRoot } finally { Pop-Location }
    }
    $ans = Read-Host '实际与预期一致? (y=一致 / n=不一致 / s=跳过)'
    [pscustomobject]@{ 项目 = $it.item; 与预期一致 = $ans }
}

# ---- 产物 -----------------------------------------------------------------
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
$capLines = ($capture  | ForEach-Object { "| {0} | {1} | {2} | {3} |" -f $_.按键, $_.字符码, $_.键名, $_.修饰键 }) -join "`n"
$chkLines = ($checklist | ForEach-Object { "| {0} | {1} |" -f $_.项目, $_.与预期一致 }) -join "`n"

$report = @"
# IKH1RA 真机验证结果

- 终端: $term
- 时间: $stamp
- 解释器: $Python

## 阶段一: 按键捕获

| 按键 | 字符码 | 键名 | 修饰键 |
|---|---|---|---|
$capLines

## 阶段二: 应用内清单

| 项目 | 与预期一致 |
|---|---|
$chkLines

## 结论

（回填 SP5_gates_matrix.md 矩阵与 keybinding-fix-wt/README.md 状态表后删除本文件）
"@

$out = Join-Path $PSScriptRoot 'matrix_results.md'
$report | Out-File -FilePath $out -Encoding utf8
Write-Host "`n结果已写入: $out"
Write-Host '请将结果回填 SP5_gates_matrix.md 与 README.md 状态表; 全部通过后本脚本可删除。'
Read-Host '按回车退出'
