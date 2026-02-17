$repoPy = Join-Path $PSScriptRoot "apps\ivan\.venv\Scripts\python.exe"
if (Test-Path $repoPy) {
  & $repoPy "$PSScriptRoot\runapp" @args
} else {
  python "$PSScriptRoot\runapp" @args
}
exit $LASTEXITCODE
