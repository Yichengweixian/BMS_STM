$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$uv = 'D:\K5\UV4\UV4.exe'
$project = Join-Path $PSScriptRoot 'BMS_EXv1.1\BMS_EX\MDK-ARM\Appli\BMS_EX_Appli.uvprojx'
$out = Join-Path $PSScriptRoot 'evidence\runs\20261101-G03-relay-r1'
New-Item -ItemType Directory -Path $out -Force | Out-Null
foreach ($target in @('BMS_EX_Release','BMS_EX_Debug')) {
    $log = Join-Path $out ($target + '-build.log')
    $proc = Start-Process -FilePath $uv -ArgumentList @('-b',('"' + $project + '"'),'-t',$target,'-o',('"' + $log + '"')) -WindowStyle Hidden -PassThru -Wait
    Get-Content -LiteralPath $log -Tail 8
    if ($proc.ExitCode -gt 1) { exit $proc.ExitCode }
}
