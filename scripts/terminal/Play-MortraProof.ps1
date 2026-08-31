# Scene を terminal 上で1段ずつ上演する。
#
# 座標も文言も Scene から来る。ここでは作らない。
# 毎フレーム Clear-Host はしない。カーソルを原点へ戻して同じ画面を上書きする。
#
#   ライブ:  .\Play-MortraProof.ps1 -Scene build\terminal\2009G6.scene.json
#   書き出し: .\Play-MortraProof.ps1 -Scene ... -CaptureDir build\terminal\frames -Fps 24

[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Problem,
    [string]$Scene,
    [switch]$List,
    [switch]$Check,
    [int]$Cols = 100,
    [int]$Rows = 30,
    [int]$Fps = 24,
    [string]$CaptureDir,
    [switch]$NoColor
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'Mortra.Raster.psm1') -Force -DisableNameChecking

if ($Check) {
    # 端末が Braille を出せるかを、実際に出して確かめてもらう。
    $enc = [Console]::OutputEncoding.WebName
    try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { }
    $sample = -join (0x2801, 0x2803, 0x2809, 0x2847, 0x28FF, 0x2800 | ForEach-Object { [char]$_ })
    [Console]::Out.Write("  braille : [$sample]`n")
    [Console]::Out.Write("  expected: [" + [char]0x2801 + [char]0x2803 + [char]0x2809 +
                         [char]0x2847 + [char]0x28FF + [char]0x2800 + "]  (last one is blank)`n")
    "  PowerShell        $($PSVersionTable.PSVersion)"
    "  OutputEncoding    $enc -> $([Console]::OutputEncoding.WebName)"
    ""
    "  If you saw '?' the encoding is wrong. If you saw boxes, the font has no"
    "  Braille block (U+2800-28FF). Cascadia Mono and Cascadia Code have all 256;"
    "  Consolas and Ubuntu Mono have none."
    exit 0
}

$SceneDir = Join-Path $PSScriptRoot 'scenes'
$available = @(Get-ChildItem -Path $SceneDir -Filter *.json -ErrorAction SilentlyContinue |
               Sort-Object BaseName)

if ($List) {
    "  MORTRA proof scenes  ($($available.Count))"
    ""
    foreach ($f in $available) {
        $j = Get-Content -Raw -Encoding UTF8 $f.FullName | ConvertFrom-Json
        $g = $j.steps[-1]
        "    {0,-24} {1,2} steps   {2,-8} residual {3:e1} {4}" -f `
            $f.BaseName, $j.steps.Count, $g.goal_kind, $g.residual, $g.residual_unit
    }
    ""
    "  .\Play-MortraProof.ps1 <name>"
    exit 0
}

if (-not $Scene) {
    if (-not $available) { Write-Error "scenes/ に scene がありません: $SceneDir"; exit 1 }
    if ($Problem) {
        $hit = $available | Where-Object BaseName -eq $Problem
        if (-not $hit) {
            Write-Error ("'$Problem' がありません。-List で一覧が出ます。")
            exit 1
        }
        $Scene = $hit.FullName
    } else {
        # 既定は最初の1本。何も指定せずに動くようにしておく。
        $Scene = $available[0].FullName
    }
}

$ESC = [char]27
function SGR([int]$r, [int]$g, [int]$b) { "$ESC[38;2;$r;$g;${b}m" }

# MORTRA の配色
$C = @{
    Construct = SGR 255 157  46
    Theorem   = SGR 255  95 176
    Algebra   = SGR 232 238 242
    Close     = SGR  77 255 160
    Numeric   = SGR  79 195 255
    Dim       = SGR 125 145 158
    Faint     = SGR  43  55  66
}

$scn = Get-Content -Raw -Encoding UTF8 $Scene | ConvertFrom-Json

# ---- ライブ再生のときは端末の実寸に合わせる ----
# 端末より大きいフレームを書くと巻き上がり、原点へ戻しても位置がずれる。
$isLive = -not $CaptureDir
if ($isLive) {
    $winW = $null; $winH = $null
    try { $winW = [Console]::WindowWidth; $winH = [Console]::WindowHeight } catch { }
    if ($winW -and $winH) {
        # 最下行に書くと巻き上がる端末があるので1行残す
        if (-not $PSBoundParameters.ContainsKey('Cols')) { $Cols = $winW }
        if (-not $PSBoundParameters.ContainsKey('Rows')) { $Rows = $winH - 1 }
        $Cols = [Math]::Min($Cols, $winW)
        $Rows = [Math]::Min($Rows, $winH - 1)
    }
    if ($Rows -lt 14 -or $Cols -lt 40) {
        Write-Error "端末が小さすぎます（${Cols}x${Rows}）。40x14 以上にしてください。"
        exit 1
    }
}

# ---- 図の座標 -> dot 座標。図全体が入る等方な変換を1つだけ作る ----
$PLOT_ROWS = $Rows - 8          # 下8行は台帳に使う
$DOTW = $Cols * 2
$DOTH = $PLOT_ROWS * 4

$xs = @(); $ys = @()
foreach ($p in $scn.points.PSObject.Properties) { $xs += $p.Value[0]; $ys += $p.Value[1] }
$x0 = ($xs | Measure-Object -Minimum).Minimum
$x1 = ($xs | Measure-Object -Maximum).Maximum
$y0 = ($ys | Measure-Object -Minimum).Minimum
$y1 = ($ys | Measure-Object -Maximum).Maximum
$padX = ($x1 - $x0) * 0.10 + 1
$padY = ($y1 - $y0) * 0.10 + 1
$x0 -= $padX; $x1 += $padX; $y0 -= $padY; $y1 += $padY
# 文字セルは幅:高さ = 1:2。dot は幅 1/2 セル、高さ 1/4 セルなので
# dot 自体はほぼ正方形になる。よって縦横で同じ倍率を使う。
$sx = ($DOTW - 1) / ($x1 - $x0)
$sy = ($DOTH - 1) / ($y1 - $y0)
$s  = [Math]::Min($sx, $sy)
$s2 = $s
$offX = ($DOTW - ($x1 - $x0) * $s) / 2
$offY = ($DOTH - ($y1 - $y0) * $s2) / 2

function PX([double]$x) { $offX + ($x - $x0) * $s }
function PY([double]$y) { $offY + ($y - $y0) * $s2 }   # SVG は下向きが正。そのまま使う

# ---- タイムライン。1段 = 表示 + 描画 + 保持 ----
$FT = 1000.0 / $Fps
$steps = @($scn.steps)
$plan = New-Object System.Collections.Generic.List[object]
for ($i = 0; $i -lt $steps.Count; $i++) {
    $st = $steps[$i]
    $isGoal = $false
    if ($st.PSObject.Properties.Name -contains 'is_goal') { $isGoal = [bool]$st.is_goal }
    $type   = [Math]::Max(8, $st.text.Length)      # 1文字1フレーム
    $draw   = if ($st.segments.Count -gt 0) { 14 } else { 6 }
    $hold   = if ($isGoal) { 40 } else { 8 }
    $plan.Add([pscustomobject]@{ Index=$i; Step=$st; IsGoal=$isGoal;
                                 Type=$type; Draw=$draw; Hold=$hold })
}
$totalFrames = ($plan | Measure-Object -Property Type -Sum).Sum +
               ($plan | Measure-Object -Property Draw -Sum).Sum +
               ($plan | Measure-Object -Property Hold -Sum).Sum

function Build-Frame {
    param([int]$Upto, [double]$TypeP, [double]$DrawP)

    $cv = New-MortraCanvas -Cols $Cols -Rows $Rows

    # 完了した段
    for ($k = 0; $k -lt $Upto; $k++) {
        $st = $steps[$k]
        $col = if ($st.PSObject.Properties.Name -contains 'is_goal' -and $st.is_goal) { $C.Close } else { $C.Construct }
        foreach ($g in $st.segments) {
            Add-MortraSegment -Canvas $cv -X0 (PX $g.a[0]) -Y0 (PY $g.a[1]) `
                -X1 (PX $g.b[0]) -Y1 (PY $g.b[1]) -Color $col
        }
    }
    # 描画中の段
    if ($Upto -lt $steps.Count -and $DrawP -gt 0) {
        $st = $steps[$Upto]
        $col = if ($st.PSObject.Properties.Name -contains 'is_goal' -and $st.is_goal) { $C.Close } else { $C.Theorem }
        foreach ($g in $st.segments) {
            Add-MortraSegment -Canvas $cv -X0 (PX $g.a[0]) -Y0 (PY $g.a[1]) `
                -X1 (PX $g.b[0]) -Y1 (PY $g.b[1]) -Color $col -Progress $DrawP
        }
    }

    # 点。定義済みのものだけ。名前は文字セルに焼く
    $shown = @{}
    for ($k = 0; $k -le [Math]::Min($Upto, $steps.Count - 1); $k++) {
        foreach ($n in $steps[$k].points) { $shown[$n] = $k }
    }
    foreach ($n in $shown.Keys) {
        $p = $scn.points.$n
        $dx = [int][Math]::Round((PX $p[0])); $dy = [int][Math]::Round((PY $p[1]))
        $col = if ($shown[$n] -eq $Upto) { $C.Numeric } else { $C.Algebra }
        foreach ($o in @(@(0,0),@(1,0),@(0,1),@(1,1))) {
            Set-MortraDot -Canvas $cv -X ($dx+$o[0]) -Y ($dy+$o[1]) -Color $col
        }
        Set-MortraCellText -Canvas $cv -Col ([int][Math]::Floor($dx/2)+1) `
            -Row ([int][Math]::Floor($dy/4)) -Text $n -Color $col
    }

    # 台帳
    $base = $Rows - 7
    Set-MortraCellText -Canvas $cv -Col 0 -Row $base -Text ('─' * $Cols) -Color $C.Faint
    Set-MortraCellText -Canvas $cv -Col 0 -Row ($base+1) `
        -Text "MORTRA   $($scn.problem)" -Color $C.Algebra
    Set-MortraCellText -Canvas $cv -Col ($Cols-26) -Row ($base+1) `
        -Text "exact / no LLM in path" -Color $C.Dim

    # いま実行中の構成文を1文字ずつ
    if ($Upto -lt $steps.Count) {
        $t = $steps[$Upto].text
        $n = [int][Math]::Round($t.Length * [Math]::Min($TypeP,1.0))
        $shownText = $t.Substring(0, [Math]::Min($n, $t.Length))
        $isG = $steps[$Upto].PSObject.Properties.Name -contains 'is_goal' -and $steps[$Upto].is_goal
        $prefix = if ($isG) { '? ' } else { "$($Upto+1)/$($steps.Count-1)  " }
        Set-MortraCellText -Canvas $cv -Col 0 -Row ($base+3) `
            -Text ($prefix + $shownText) -Color $(if ($isG) { $C.Close } else { $C.Construct })
        if ($n -lt $t.Length) {
            Set-MortraCellText -Canvas $cv -Col ($prefix.Length + $n) -Row ($base+3) `
                -Text '_' -Color $C.Dim
        }
    }

    # 目標が閉じたら測定値を出す。測っていないものに VERIFIED は出さない。
    $last = $steps[$steps.Count-1]
    if ($Upto -ge $steps.Count - 1 -and $DrawP -ge 1.0 -and
        $last.PSObject.Properties.Name -contains 'residual') {
        $ok = $last.PSObject.Properties.Name -contains 'verified' -and $last.verified
        $tag = if ($ok) { '[ VERIFIED ]' } else { '[ NOT VERIFIED ]' }
        $col = if ($ok) { $C.Close } else { $C.Theorem }
        Set-MortraCellText -Canvas $cv -Col 0 -Row ($base+5) `
            -Text ("$tag  " + $last.goal_kind + " " + ($last.goal_points -join ' ')) -Color $col
        Set-MortraCellText -Canvas $cv -Col 0 -Row ($base+6) `
            -Text ("residual {0:0.000000} {1}   measured on the figure's own coordinates" `
                   -f $last.residual, $last.residual_unit) -Color $C.Numeric
    }
    ConvertTo-MortraText -Canvas $cv -NoColor:$NoColor
}

# ---- 上演 ----
$capture = [bool]$CaptureDir
if ($capture) {
    New-Item -ItemType Directory -Force -Path $CaptureDir | Out-Null
    # .NET の現在ディレクトリは PowerShell の場所と別なので、絶対パスに直す
    $CaptureDir = (Resolve-Path -LiteralPath $CaptureDir).ProviderPath
}

$live = -not $capture
$fi = 0
$prevEnc = $null

if ($live) {
    # [Console]::Out は OutputEncoding を通る。既定の cp932 だと Braille が
    # 全て '?' に落ちる。PowerShell の出力ストリームとは別経路なので、
    # ここで明示的に UTF-8 にする。
    try {
        $prevEnc = [Console]::OutputEncoding
        [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    } catch { }
    # 代替画面バッファへ移る。終わったら元の画面と履歴がそのまま戻る。
    [Console]::Out.Write("$ESC[?1049h$ESC[?25l$ESC[2J")
}

# Start-Sleep は分解能が粗く、毎フレーム遅れが積もる。
# 経過時間から目標時刻を出して、そこまで待つ。
$sw = [System.Diagnostics.Stopwatch]::StartNew()

try {
    foreach ($ph in $plan) {
        $nType = [int]$ph.Type; $nDraw = [int]$ph.Draw; $nHold = [int]$ph.Hold
        $seq = New-Object System.Collections.Generic.List[double[]]
        for ($k = 1; $k -le $nType; $k++) { $seq.Add([double[]]@(($k / $nType), 0.0)) }
        for ($k = 1; $k -le $nDraw; $k++) { $seq.Add([double[]]@(1.0, ($k / $nDraw))) }
        for ($k = 1; $k -le $nHold; $k++) { $seq.Add([double[]]@(1.0, 1.0)) }
        foreach ($t in $seq) {
            $frame = Build-Frame -Upto $ph.Index -TypeP $t[0] -DrawP $t[1]
            if ($capture) {
                $p = Join-Path $CaptureDir ("f{0:D5}.txt" -f $fi)
                [System.IO.File]::WriteAllText($p, $frame, [System.Text.UTF8Encoding]::new($false))
            } else {
                # ESC[H で原点へ。SetCursorPosition より端末に依存しない。
                [Console]::Out.Write("$ESC[H" + $frame)
                $wait = ($fi + 1) * $FT - $sw.Elapsed.TotalMilliseconds
                if ($wait -gt 1) { Start-Sleep -Milliseconds ([int]$wait) }
                if ([Console]::KeyAvailable) {
                    $key = [Console]::ReadKey($true)
                    if ($key.Key -eq 'Escape' -or $key.Key -eq 'Q') { throw [OperationCanceledException]::new() }
                }
            }
            $fi++
        }
    }
} catch [OperationCanceledException] {
    # 中断。finally で画面を戻す
} finally {
    if ($live) {
        [Console]::Out.Write("$ESC[?25h$ESC[?1049l")
        if ($prevEnc) { try { [Console]::OutputEncoding = $prevEnc } catch { } }
    }
}

if ($live) {
    "  $($scn.problem)   段 $($steps.Count)   frames $fi   " +
    ("目標 {0:F1}s / 実測 {1:F1}s" -f ($fi / $Fps), $sw.Elapsed.TotalSeconds)
} else {
    "  段     $($steps.Count)"
    "  frames $fi   @ ${Fps}fps = {0:F1}s" -f ($fi / $Fps)
    "  -> $CaptureDir"
}
