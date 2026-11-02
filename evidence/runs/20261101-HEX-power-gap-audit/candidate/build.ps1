param(
    [string]$Compiler = 'D:\Program Files\JetBrains\CLion 2025.2.3\bin\mingw\bin\gcc.exe'
)
$ErrorActionPreference = 'Stop'
$candidateRoot = $PSScriptRoot
$candidateCompiler = (Resolve-Path -LiteralPath $Compiler).Path
$env:PATH = (Split-Path -Parent $candidateCompiler) + ';' + $env:PATH
$candidateExecutable = Join-Path $candidateRoot 'test_pwm_oneshot.exe'
$candidateLog = Join-Path $candidateRoot 'test-results.txt'
$candidateVersion = (& $candidateCompiler --version | Select-Object -First 1)
$candidateFlags = @('-std=c11', '-Wall', '-Wextra', '-Werror', '-Wconversion', '-Wshadow', '-pedantic', '-O2')
& $candidateCompiler @candidateFlags (Join-Path $candidateRoot 'pwm_oneshot.c') (Join-Path $candidateRoot 'test_pwm_oneshot.c') -o $candidateExecutable
$candidateCompileExit = $LASTEXITCODE
if ($candidateCompileExit -ne 0) { throw "Compilation failed: $candidateCompileExit" }
$candidateOutput = & $candidateExecutable 2>&1
$candidateTestExit = $LASTEXITCODE
$candidateOutput | Set-Content -LiteralPath $candidateLog -Encoding UTF8
$candidateOutput
$candidateHashes = [ordered]@{}
foreach ($candidateName in @('pwm_oneshot.c', 'pwm_oneshot.h', 'test_pwm_oneshot.c', 'build.ps1')) {
    $candidateHashes[$candidateName] = (Get-FileHash -LiteralPath (Join-Path $candidateRoot $candidateName) -Algorithm SHA256).Hash.ToLowerInvariant()
}
$candidateResult = [ordered]@{
    scope = 'host C simulation; no MCU adapter, power output, flashing or board validation'
    compiler = $candidateCompiler
    compiler_version = $candidateVersion
    flags = $candidateFlags
    compile_exit_code = $candidateCompileExit
    test_exit_code = $candidateTestExit
    test_groups = 16
    source_sha256 = $candidateHashes
    board_profile_provided = $false
}
$candidateResult | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $candidateRoot 'validation.json') -Encoding UTF8
if ($candidateTestExit -ne 0) { throw "Tests failed: $candidateTestExit" }
