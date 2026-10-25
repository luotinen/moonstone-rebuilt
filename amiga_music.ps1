# Moonstone Rebuilt: plays the Amiga intro and ending music (D8) beside DOSBox-X. Started by Start.bat when
# AMIGA.FLG exists. DOSBox-X shows the running DOS program in its window title ("...: INTR - 4000 cycles/ms").
# MS.EXE runs INTR.EXE first for the intro, then MAIN.EXE, and INTR.EXE again for the ending, so INTR before the
# first MAIN is the intro and INTR after it is the ending. The DOS intro and ending tunes are muted copies meanwhile.
# Music stops as soon as INTR ends (also when the intro is skipped) and when DOSBox-X closes.
param([int]$WaitSeconds = 60, [string]$TitleFile = '')
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$wav = @{ intro = Join-Path $dir '_music\amiga\intro.wav'; ending = Join-Path $dir '_music\amiga\ending.wav' }
$players = @{}
foreach ($k in $wav.Keys) {
    if (-not (Test-Path $wav[$k])) { exit 1 }
    $p = New-Object System.Media.SoundPlayer $wav[$k]
    $p.Load()
    $players[$k] = $p
}

# Test hook: with -TitleFile, read window titles from a text file (one per line) instead of DOSBox-X.
if ($TitleFile) {
    $titles = Get-Content $TitleFile
    $script:i = 0
    function Get-Title { if ($script:i -ge $titles.Count) { return $null }; $t = $titles[$script:i]; $script:i++; return $t }
} else {
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    $proc = $null
    while (-not $proc -and (Get-Date) -lt $deadline) {
        $proc = Get-Process -Name 'dosbox-x' -ErrorAction SilentlyContinue |
            Where-Object { $_.MainWindowTitle -like '*Moonstone Rebuilt*' } | Select-Object -First 1
        if (-not $proc) { Start-Sleep -Milliseconds 250 }
    }
    if (-not $proc) { exit 0 }
    function Get-Title { $proc.Refresh(); if ($proc.HasExited) { return $null }; return $proc.MainWindowTitle }
}

# Log of every distinct window title and every start or stop, for checking what happened (kept to the last run).
$log = Join-Path $dir '_music\amiga\amiga_music.log'
if (-not $TitleFile) { Set-Content -Path $log -Value "$(Get-Date -Format s) started" -Encoding UTF8 }
function Write-Log($text) {
    if ($TitleFile) { $text } else { Add-Content -Path $log -Value "$(Get-Date -Format 'HH:mm:ss.fff') $text" -Encoding UTF8 }
}

$seenMain = $false
$playing = $null
$lastTitle = $null
while ($true) {
    $title = Get-Title
    if ($null -eq $title) { break }
    $shown = $title -replace ', FPS +\d+', ''                 # the FPS count changes every second
    if ($shown -ne $lastTitle) { Write-Log "title: $shown"; $lastTitle = $shown }
    # Only a title that names the running program changes anything. Windows can return an empty or different title
    # for a moment (e.g. while DOSBox-X captures the mouse); stopping then would restart the music from the beginning.
    if ($title -match ': ([A-Z0-9_\-]+) - ') {
        $program = $Matches[1]
        $want = $null
        if ($program -eq 'INTR') { $want = if ($seenMain) { 'ending' } else { 'intro' } }
        elseif ($program -in 'MAIN', 'PREFIGHT', 'PRETURN') { $seenMain = $true }
        if ($want -ne $playing) {
            if ($playing) { $players[$playing].Stop() }
            if ($want) { $players[$want].Play() }
            $playing = $want
            Write-Log ("{0} -> {1}" -f $program, ($(if ($want) { $want } else { 'stop' })))
        }
    }
    if (-not $TitleFile) { Start-Sleep -Milliseconds 200 }
}
if ($playing) { $players[$playing].Stop() }
Write-Log 'DOSBox-X closed'
