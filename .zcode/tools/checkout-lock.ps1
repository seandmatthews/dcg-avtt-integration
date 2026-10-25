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
# Invariant (ticket 20): the steal age must be strictly less than the longest
# acquire wait any caller passes (the ticket implementer waits 1800s on "main",
# avtt-ticket-implementer.dwf.ts) - the two numbers are one contract, not two
# knobs. If the steal age reached the acquire timeout, a lock left by a crashed
# run could never be stolen before every waiter gave up; at 1500s a waiter that
# has waited 25 minutes may steal a lock 25 minutes old. Change them together.
# (This file stays pure ASCII: powershell.exe 5.1 reads a BOM-less script as
# ANSI, and a multi-byte char inside a quoted string garbles into a quote and
# breaks the parse.)
$maxAgeSec = 1500

function Get-AgeSeconds([string]$p) {
	# DateTimeOffset.Parse honors the stamp's trailing Z (UTC) regardless of the
	# machine's timezone - and avoids [System.DateTimeStyles], which this box's
	# PowerShell 5.1 refuses to resolve.
	try {
		$raw = Get-Content $p -Raw
	} catch {
		# Unreadable right now: the creator's FileShare::None write handle is
		# still open (the window between File::Open and Close). That is a LIVE
		# holder mid-write, never a crash - read as fresh (0) so it is never
		# stolen; the next poll reads the finished stamp.
		return 0
	}
	try {
		$stamp = [DateTimeOffset]::Parse($raw.Trim())
		return ([DateTimeOffset]::UtcNow - $stamp).TotalSeconds
	} catch {
		# Readable but empty/corrupt (ticket 20): the holder crashed between
		# creating the file and writing the stamp, or the file is garbage.
		# Reads as infinitely old - stealable immediately. Returning 0 here
		# (the old behavior) made a corrupt lock permanently unstealable.
		return [double]::PositiveInfinity
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
			$age = Get-AgeSeconds $lockPath
			if ([double]::IsInfinity($age)) {
				Write-Output "held (corrupt stamp - reads as infinitely old, stealable)"
			} else {
				Write-Output "held (age $([int]$age)s)"
			}
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
