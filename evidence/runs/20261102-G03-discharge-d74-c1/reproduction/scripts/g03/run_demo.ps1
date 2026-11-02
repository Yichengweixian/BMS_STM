param(
    [ValidateSet('Query','Live')][string]$Mode='Query',
    [ValidateSet('D90','D80','D74')][string]$Point='D90',
    [string]$Port='COM12',
    [switch]$BenchReady
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$evidenceRoot=Join-Path $projectRoot 'evidence/runs/20261102-G03-discharge-d74-c1'
$pythonExe='C:/Users/ADMIN/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$serialVendor='C:/Users/ADMIN/.codex/visualizations/2026/11/02/01a19a8a-4630-7842-89f5-2b0cccea4066/g03-sprint-work/vendor'
$capture=Join-Path $PSScriptRoot 'power_capture.py'
$firmwareImage=Join-Path $evidenceRoot 'firmware/BMS_PWM_Power_Release/BMS_PWM_Power_Release.hex'
$imageSha='001577eeccc6ab3d264283cb4d85be17e19051a08dccc2eb983f02fd9da2d4ab'
if(!(Test-Path -LiteralPath $pythonExe)){throw 'Python runtime missing; install Python and pyserial and update this local runtime path.'}
if((Get-FileHash -LiteralPath $firmwareImage -Algorithm SHA256).Hash.ToLowerInvariant() -ne $imageSha){throw 'Firmware file hash mismatch.'}
if($Mode -eq 'Live' -and !$BenchReady){throw 'Live requires -BenchReady: confirm wiring, 3.500V/CC0.600A/OCP0.550A/OVP3.650V, load, empty charge port, and no CC/trip. This flag cannot replace those checks.'}
$env:PYTHONUTF8='1';$env:PYTHONPATH=$serialVendor
$sessionRoot=Join-Path $projectRoot ('evidence/runs/demo-'+(Get-Date -Format 'yyyyMMdd-HHmmssfff'))
$queryOut=Join-Path $sessionRoot 'default-off-query'
& $pythonExe $capture --port $Port --mode query --out $queryOut --image $firmwareImage --sha256 $imageSha
if($LASTEXITCODE -ne 0){throw 'Status query failed. No start sent.'}
if($Mode -eq 'Query'){Write-Output $queryOut;exit 0}
$queryResult=Get-Content -LiteralPath (Join-Path $queryOut 'result.json') -Raw | ConvertFrom-Json
foreach($field in @('phase','faults','used','owned','bits')){if($queryResult.status.$field -ne 0){throw "Not unused/default off: $field. No automatic RESET or retry."}}
$dry=Get-Content -LiteralPath (Join-Path $evidenceRoot 'new-image-dry-03/result.json') -Raw | ConvertFrom-Json
if($dry.verdict -ne 'pass'){throw 'New-image rehearsal evidence unavailable.'}
$profile=if($Point -eq 'D90'){0x50393303}elseif($Point -eq 'D80'){0x50393304}else{0x50393402}
$shortPath=if($Point -eq 'D74'){'evidence/runs/20261102-G03-discharge-d74-c1/live-d74-short-01/result.json'}elseif($Point -eq 'D90'){'evidence/runs/20261102-G03-discharge-sprint-r2/live-d90-01/result.json'}else{'evidence/runs/20261102-G03-discharge-sprint-r4/live-d80-short-01/result.json'}
if((Get-Content -LiteralPath (Join-Path $projectRoot $shortPath) -Raw | ConvertFrom-Json).verdict -ne 'pass'){throw 'Required same-D short-point evidence unavailable.'}
$contract=[ordered]@{profile=$profile;firmware_sha256=$imageSha;source_wiring_confirmed=$true;source_settings_confirmed=$true;source_cv_confirmed=$true;no_real_cells=$true;load_connected=$true;charge_port_open=$true;new_image_default_off_verified=$true;dry_run_passed=$true;source_paths_reviewed=$true;operator_assertion='-BenchReady supplied after checking operation-guide.md';prior_same_D_short_evidence=$shortPath;dry_evidence='c1 D74 dry and affected offline checks; r3 long deadline logic unchanged';created_utc=[DateTime]::UtcNow.ToString('o');physical_short_current_ceiling_confirmed=$false}
$contractPath=Join-Path $sessionRoot 'contract.json'
$contract | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $contractPath -Encoding UTF8
$liveOut=Join-Path $sessionRoot ('live-'+$Point)
Write-Output "Starting ONE fixed-D two-second run: $Point. No reset, sweep, or retry. Ctrl+C sends STOP."
& $pythonExe $capture --port $Port --mode live --profile $profile --contract $contractPath --out $liveOut --image $firmwareImage --sha256 $imageSha
if($LASTEXITCODE -ne 0){throw "Run failed or interrupted; preserve $liveOut. No retry."}
Write-Output "Completed. Record DMM voltage and PSU currents separately, then all three source outputs OFF. Evidence: $liveOut"

