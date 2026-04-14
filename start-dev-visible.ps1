$ErrorActionPreference = "Stop"
$RootPath = if ($PSScriptRoot) {
	(Resolve-Path $PSScriptRoot).Path
} else {
	(Get-Location).Path
}

Set-Location $RootPath
& (Join-Path $RootPath "start-dev.ps1") -VisibleWindows