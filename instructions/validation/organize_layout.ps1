# One-time layout migration. Literal paths only; no delete, overwrite, or executable launch.
$ErrorActionPreference = 'Stop'
$bmsWorkspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
function Get-BmsContainedPath([string]$Relative) {
    $absolute = [IO.Path]::GetFullPath((Join-Path $bmsWorkspace $Relative))
    if (-not $absolute.StartsWith($bmsWorkspace + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes workspace: $absolute"
    }
    return $absolute
}
$moves = @(
    @('基于STM32N6的智能BMS边缘智能系统设计.pptx', 'docs\course\基于STM32N6的智能BMS边缘智能系统设计.pptx'),
    @('任务2恒流控制实验_实验步骤.docx', 'docs\course\任务2恒流控制实验_实验步骤.docx'),
    @('BMS_EX工程模板使用说明.docx', 'docs\manuals\BMS_EX工程模板使用说明.docx'),
    @('BMS电池测试上位机操作手册（图文版）.docx', 'docs\manuals\BMS电池测试上位机操作手册（图文版）.docx'),
    @('STM32N6软件安装.docx', 'docs\manuals\STM32N6软件安装.docx'),
    @('目录逐文件说明.html', 'docs\guides\目录逐文件说明.html'),
    @('BMS系统原理与开发路线.html', 'docs\guides\BMS系统原理与开发路线.html'),
    @('BMS_Appli.hex', 'firmware\prebuilt\BMS_Appli.hex'),
    @('BMS上位机d.zip', 'tools\host\BMS上位机d.zip'),
    @('MX25UM25645G_ATK-CNN647B_ExtMe.rar', 'tools\flash-loaders\MX25UM25645G_ATK-CNN647B_ExtMe.rar'),
    @('MX25UM25645G_ATK-CNN647B_ExtMemLoader.rar', 'tools\flash-loaders\MX25UM25645G_ATK-CNN647B_ExtMemLoader.rar'),
    @('MX25UM25645G_ATK-CNN647B-FLM.rar', 'tools\flash-loaders\MX25UM25645G_ATK-CNN647B-FLM.rar'),
    @('STM32CubeProgrammer 软件安装程序-win.zip', 'tools\installers\STM32CubeProgrammer 软件安装程序-win.zip'),
    @('BMS执行规范', 'instructions')
)
# Verify every source and final absolute target before moving any directory.
foreach ($pair in $moves) {
    $source = Get-BmsContainedPath $pair[0]
    $target = Get-BmsContainedPath $pair[1]
    if (-not (Test-Path -LiteralPath $source)) { throw "Source missing: $source" }
    if (Test-Path -LiteralPath $target) { throw "Refusing to overwrite: $target" }
    $resolved = (Resolve-Path -LiteralPath $source).Path
    if (-not $resolved.StartsWith($bmsWorkspace + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Resolved source escapes workspace: $resolved" }
    if ((Get-Item -LiteralPath $source).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse source requires separate review: $source" }
}
$codeRoot = Get-BmsContainedPath 'BMS_EXv1.1'
$codeBefore = @(Get-ChildItem -LiteralPath $codeRoot -Recurse -File -Force | ForEach-Object {
    [ordered]@{ path = [IO.Path]::GetRelativePath($bmsWorkspace, $_.FullName).Replace('\','/'); bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower() }
})
$records = @()
foreach ($pair in $moves) {
    $source = Get-BmsContainedPath $pair[0]
    $target = Get-BmsContainedPath $pair[1]
    if (Test-Path -LiteralPath $source -PathType Leaf) {
        $records += [ordered]@{ before = $pair[0].Replace('\','/'); after = $pair[1].Replace('\','/'); sha256_before = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower() }
    }
}
$history = Get-BmsContainedPath 'BMS执行规范\references\history'
New-Item -ItemType Directory -Path $history | Out-Null
Copy-Item -LiteralPath (Get-BmsContainedPath '目录逐文件说明.html') -Destination (Join-Path $history '目录逐文件说明.before-layout.html')
Copy-Item -LiteralPath (Get-BmsContainedPath 'BMS系统原理与开发路线.html') -Destination (Join-Path $history 'BMS系统原理与开发路线.before-layout.html')
Copy-Item -LiteralPath (Get-BmsContainedPath 'BMS执行规范\references\source-manifest.json') -Destination (Join-Path $history 'source-manifest.before-layout.json')
foreach ($pair in $moves) {
    $source = Get-BmsContainedPath $pair[0]
    $target = Get-BmsContainedPath $pair[1]
    $parent = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
    Move-Item -LiteralPath $source -Destination $target
}
foreach ($record in $records) {
    $record.sha256_after_move = (Get-FileHash -LiteralPath (Get-BmsContainedPath $record.after) -Algorithm SHA256).Hash.ToLower()
    if ($record.sha256_before -ne $record.sha256_after_move) { throw "File changed during move: $($record.after)" }
}
$report = [ordered]@{
    migrated_at = [DateTimeOffset]::Now.ToString('o')
    root = $bmsWorkspace
    scope = 'File relocation only; HTML references and instruction activation are updated afterwards.'
    mappings = @($moves | ForEach-Object { [ordered]@{ before = $_[0].Replace('\','/'); after = $_[1].Replace('\','/') } })
    relocated_files = $records
    untouched_keil_files = $codeBefore
    files_deleted = 0
    all_moved_regular_files_identical = $true
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Get-BmsContainedPath 'instructions\references\layout-migration.json') -Encoding utf8
[ordered]@{ moved_entries = $moves.Count; moved_files_verified = $records.Count; keil_files_baselined = $codeBefore.Count; files_deleted = 0; workspace = $bmsWorkspace } | ConvertTo-Json
