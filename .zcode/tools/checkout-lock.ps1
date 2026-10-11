# checkout-lock.ps1 - cross-process mutex for the shared main checkout.
#
# The pigeon-ticket-pipeline workflow (.zcode/workflows/) holds this lock around
# every section that touches the shared main checkout: the baseline snapshot
# commit, the baseline gate suite, the merge into main, the post-merge gate
# suite and any revert. Concurrent pipeline runs are fully parallel inside their
# own worktrees; this serializes exactly the part that cannot overlap (a merge
# race, and concurrent --import writers fighting over main's .godot/ cache).
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File checkout-lock.ps1 acquire <name> <timeoutSec>
#   powershell -NoProfile -ExecutionPolicy Bypass -File checkout-lock.ps1 release <name>
#   powershell -NoProfile -ExecutionPolicy Bypass -File checkout-lock.ps1 status <name>
#
# Locks are files under .locks/ next to this script. Creation with
# FileMode::CreateNew + FileShare::None is the atomic test-and-set. The file
# records its acquire time (ISO 8601 UTC); a lock older than $maxAgeSec is
# stale - its holder crashed and can never release - and the next acquirer
# steals it.

param(
	[Parameter(Mandatory = $true)][string]$Action,
	[Parameter(Mandatory = $true)][string]$Name,
	[int]$TimeoutSec = 1800
)

$ErrorActionPreference = "Stop"
$lockDir = Join-Path $PSScriptRoot "locks"
New-Item -ItemType Directory -Force -Path $lockDir | Out-Null
$lockPath = Join-Path $lockDir "$Name.lock"
$maxAgeSec = 3600

function Get-AgeSeconds([string]$p) {
	# DateTimeOffset.Parse honors the stamp's trailing Z (UTC) regardless of the
	# machine's timezone — and avoids [System.DateTimeStyles], which this box's
	# PowerShell 5.1 refuses to resolve.
	try {
		$stamp = [DateTimeOffset]::Parse((Get-Content $p -Raw).Trim())
		return ([DateTimeOffset]::UtcNow - $stamp).TotalSeconds
	} catch {
		return 0
	}
}

switch ($Action) {
	"acquire" {
		$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSec)
		while ($true) {
			try {
				$stamp = [DateTime]::UtcNow.ToString("o")
				$bytes = [System.Text.Encoding]::UTF8.GetBytes($stamp)
				$fs = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
				$fs.Write($bytes, 0, $bytes.Length)
				$fs.Close()
				exit 0
			} catch [System.IO.IOException] {
				if ((Test-Path $lockPath) -and ((Get-AgeSeconds $lockPath) -gt $maxAgeSec)) {
					# Stale: the holder crashed without releasing. Steal and retry.
					Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
					continue
				}
				if ([DateTime]::UtcNow -ge $deadline) {
					Write-Output "TIMEOUT: lock '$Name' still held after ${TimeoutSec}s"
					exit 1
				}
				Start-Sleep -Milliseconds 500
			}
		}
	}
	"release" {
		Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
		exit 0
	}
	"status" {
		if (Test-Path $lockPath) {
			Write-Output "held (age $([int](Get-AgeSeconds $lockPath))s)"
			exit 1
		}
		Write-Output "free"
		exit 0
	}
	default {
		Write-Output "unknown action '$Action'"
		exit 2
	}
}
