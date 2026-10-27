# Nadzor poslova na laptopu (pokreće ga Windows planer zadataka: „Kontrola - nadzor", pri prijavi i na 10 min).
# Jedan primerak radi stalno i na 60 s proverava da li rade poslovi koji treba da rade; ako ne rade, pokreće ih.
# Režim: D:\VAJB\kontrolaizbora\zadaci\rezim.json  {"rezim": "izbori" | "proba" | "stop", "proba_do": "2026-10-22T18:00"}
$ErrorActionPreference = 'Continue'
$Base = 'D:\VAJB\kontrolaizbora'; $Repo = "$Base\repo"; $Logs = "$Base\logovi"
$env:PYTHONUTF8 = '1'; $env:KONTROLA_LOCKDIR = "$Base\zadaci"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
New-Item -ItemType Directory -Force $Logs | Out-Null
$mtx = New-Object System.Threading.Mutex($false, 'Global\KontrolaNadzor')
if (-not $mtx.WaitOne(0)) { exit 0 }   # već radi drugi nadzor
Set-Location $Repo
function L($m) {
  "$(Get-Date -Format 'dd.MM. HH:mm:ss') $m" | Out-File "$Logs\nadzor.txt" -Append -Encoding utf8
  try { $m | python tools\dnevnik.py laptop-nadzor 2>&1 | Out-Null } catch {}
}
function Rezim {
  try { return Get-Content "$Base\zadaci\rezim.json" -Raw | ConvertFrom-Json } catch { return [pscustomobject]@{ rezim = 'izbori' } }
}
function Poslovi($r) {
  $p = @()
  if ($r.rezim -eq 'izbori') {
    $od = Get-Date '2026-10-25T19:40:00'
    $p += @{ ime='rezerva';   kljuc='rik_live.py';         od=$od; do=(Get-Date '2026-10-28T12:00:00'); arg='tools\rik_live.py --standby --minutes 960' }
    $p += @{ ime='zapisnici'; kljuc='laptop_zapisnici.py'; od=$od; do=(Get-Date '2026-10-28T12:00:00'); arg="tools\laptop_zapisnici.py --dir $Base\zapisnici --until 2026-10-28T12:00 --site $Repo\public" }
    $p += @{ ime='izmene';    kljuc='laptop_izmene.py';    od=(Get-Date '2026-10-23T11:00:00'); do=(Get-Date '2026-10-25T19:00:00'); arg='tools\laptop_izmene.py --until 2026-10-25T19:00' }
    $p += @{ ime='citanje';   kljuc='laptop_citanje.py';   od=$od; do=(Get-Date '2026-10-28T12:00:00'); arg="tools\laptop_citanje.py --dir $Base\zapisnici --until 2026-10-28T12:00"; ollama=$true }
  } elseif ($r.rezim -eq 'proba') {
    $do = Get-Date $r.proba_do; $u = $do.ToString('yyyy-MM-ddTHH:mm')
    $p += @{ ime='rezerva-proba';   kljuc='rik_live.py';         od=(Get-Date).AddMinutes(-1); do=$do; arg='tools\rik_live.py --standby --sim --minutes 600' }
    $p += @{ ime='zapisnici-proba'; kljuc='laptop_zapisnici.py'; od=(Get-Date).AddMinutes(-1); do=$do; arg="tools\laptop_zapisnici.py --sim --dir $Base\proba_zap --until $u --site $Repo\public" }
    $p += @{ ime='citanje-proba';   kljuc='laptop_citanje.py';   od=(Get-Date).AddMinutes(-1); do=$do; arg="tools\laptop_citanje.py --sim --dir $Base\proba_zap --until $u"; ollama=$true }
    $p += @{ ime='izmene';    kljuc='laptop_izmene.py';    od=(Get-Date '2026-10-23T11:00:00'); do=(Get-Date '2026-10-25T19:00:00'); arg='tools\laptop_izmene.py --until 2026-10-25T19:00' }  # rešenja se čitaju i tokom probe
  }
  return $p
}
function Pocisti($r) {
  # posle promene režima: gasi poslove pogrešne vrste (proba = --sim)
  foreach ($pr in @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'rik_live\.py|laptop_zapisnici\.py|laptop_citanje\.py' -and $_.CommandLine -notlike '*nadzor*' })) {
    $sim = $pr.CommandLine -like '*--sim*'
    $los = ($r.rezim -eq 'stop') -or ($r.rezim -eq 'izbori' -and $sim) -or ($r.rezim -eq 'proba' -and -not $sim)
    if ($los) { L "gasim posao druge vrste (režim $($r.rezim)): $($pr.ProcessId) $($pr.CommandLine)"; Stop-Process -Id $pr.ProcessId -Force -ErrorAction SilentlyContinue }
  }
}
function Radi($kljuc) {
  return @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*$kljuc*" -and $_.CommandLine -notlike '*nadzor*' }).Count -gt 0
}
L "nadzor start (PID $PID)"
$poslednjiPull = Get-Date '2000-01-01'; $poslednjeJavljanje = Get-Date
Register-EngineEvent PowerShell.Exiting -Action { "$(Get-Date -Format 'dd.MM. HH:mm:ss') nadzor se gasi (PID $PID)" | Out-File "D:\VAJB\kontrolaizbora\logovi\nadzor.txt" -Append -Encoding utf8 } | Out-Null
$poslednjiRezim = $null
while ($true) {
 try {
  $r = Rezim; $sad = Get-Date
  if ($r.rezim -ne $poslednjiRezim) { if ($poslednjiRezim) { L "režim promenjen: $poslednjiRezim -> $($r.rezim)" }; Pocisti $r; $poslednjiRezim = $r.rezim }
  if ($r.rezim -eq 'stop') { Start-Sleep 60; continue }
  $aktivni = @(Poslovi $r | Where-Object { $sad -ge $_.od -and $sad -lt $_.do })
  $treba = @($aktivni | Where-Object { -not (Radi $_.kljuc) })
  if ($treba.Count -gt 0 -and ($sad - $poslednjiPull).TotalMinutes -gt 10) {
    # public/data/live na laptopu piše rezerva (rik_live) – to je radna kopija, pravi podaci su na grani uzivo; inače pull puca
    $g = cmd /c "git checkout -q main 2>&1 && git checkout -q -- public/data/live 2>&1 && git clean -fdq public/data/live 2>&1 && git pull -q --rebase --autostash 2>&1"
    if ($LASTEXITCODE -ne 0) { L "git pull nije uspeo: $g" }
    $poslednjiPull = $sad
  }
  foreach ($j in $treba) {
    if ($j.ollama -and -not (Get-Process ollama -ErrorAction SilentlyContinue)) {
      $oa = "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
      if (Test-Path $oa) { Start-Process $oa; L "pokrećem Ollama"; Start-Sleep 20 } else { L "NEMA Ollama na $oa" }
    }
    $log = "$Logs\$($j.ime).txt"
    Start-Process -FilePath 'cmd.exe' -ArgumentList "/c python $($j.arg) >> `"$log`" 2>&1" -WorkingDirectory $Repo -WindowStyle Hidden
    L "pokrenut posao $($j.ime)"
  }
  if (($sad - $poslednjeJavljanje).TotalMinutes -ge 10) {
    $st = ($aktivni | ForEach-Object { "$($_.ime)=" + $(if (Radi $_.kljuc) {'radi'} else {'NE RADI'}) }) -join ', '
    L "živ, režim $($r.rezim); $(if ($st) {$st} else {'nema aktivnih poslova u ovom trenutku'})"
    $poslednjeJavljanje = $sad
  }
 } catch { L "nadzor GREŠKA u krugu (nastavljam): $_" }
  Start-Sleep 60
}
