param(
    [int]$IntervalSec = 20,
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [switch]$AutoPush,
    [switch]$Once,
    [string]$CommitPrefix = "chore(sync): auto-sync"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$userName = if ($env:USERNAME) { $env:USERNAME } elseif ($env:USER) { $env:USER } else { "unknown-user" }
$machineName = if ($env:COMPUTERNAME) { $env:COMPUTERNAME } elseif ($env:HOSTNAME) { $env:HOSTNAME } else { "unknown-host" }
$syncTag = "$userName@$machineName"

function Write-Log {
    param([string]$Message, [string]$Color = "Gray")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$ts] $Message" -ForegroundColor $Color
}

function Get-Count {
    param([string]$Spec)
    $value = (& git rev-list --count $Spec 2>$null)
    if (-not $value) { return 0 }
    return [int]$value
}

function Is-Dirty {
    $status = (& git status --porcelain)
    return -not [string]::IsNullOrWhiteSpace($status)
}

Write-Log "Auto-sync started in $repoRoot (remote=$Remote branch=$Branch)" "Cyan"
Write-Log "Sync identity tag: $syncTag" "DarkCyan"
if ($AutoPush) {
    Write-Log "AutoPush is ENABLED: local edits will be committed and pushed." "Yellow"
} else {
    Write-Log "AutoPush is disabled: this will only auto-pull remote changes." "DarkCyan"
}

while ($true) {
    try {
        & git fetch $Remote --prune | Out-Null

        $behind = Get-Count "$Branch..$Remote/$Branch"
        $ahead = Get-Count "$Remote/$Branch..$Branch"
        $dirty = Is-Dirty

        if ($behind -gt 0) {
            if ($dirty) {
                Write-Log "Skip pull: working tree has local changes and branch is behind by $behind commit(s)." "Yellow"
            } else {
                Write-Log "Pulling $behind commit(s) from $Remote/$Branch..." "Green"
                & git pull --ff-only $Remote $Branch | Out-Null
                Write-Log "Pull complete." "Green"
            }
        }

        if ($AutoPush) {
            $dirty = Is-Dirty
            if ($dirty) {
                $msg = "$CommitPrefix [$syncTag] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
                & git add -A | Out-Null
                & git commit -m $msg | Out-Null
                Write-Log "Committed local changes." "Green"
                $ahead = Get-Count "$Remote/$Branch..$Branch"
            }

            if ($ahead -gt 0) {
                Write-Log "Pushing $ahead commit(s) to $Remote/$Branch..." "Green"
                & git push $Remote $Branch | Out-Null
                Write-Log "Push complete." "Green"
            }
        }

        if (-not $AutoPush -and $behind -eq 0) {
            Write-Log "No remote changes." "DarkGray"
        }

        if ($Once) {
            Write-Log "One-shot sync complete." "Cyan"
            break
        }
    }
    catch {
        Write-Log "Sync error: $($_.Exception.Message)" "Red"
    }

    Start-Sleep -Seconds $IntervalSec
}
