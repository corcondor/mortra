# Braille ラスタライザ。1文字 = 2x4 dot。
#
# ここは描画だけを行う。座標は呼び出し側が渡す。
# 図形を作らない、数式を作らない、文言を作らない。
#
# セル内の dot 番号と bit:
#   (0,0)=dot1 0x01   (1,0)=dot4 0x08
#   (0,1)=dot2 0x02   (1,1)=dot5 0x10
#   (0,2)=dot3 0x04   (1,2)=dot6 0x20
#   (0,3)=dot7 0x40   (1,3)=dot8 0x80
# 文字は U+2800 + bits。

Set-StrictMode -Version Latest

$script:DOTBIT = @(
    @(0x01, 0x02, 0x04, 0x40),   # 左列 row0..3
    @(0x08, 0x10, 0x20, 0x80)    # 右列 row0..3
)

function New-MortraCanvas {
    <#
    .SYNOPSIS
        cols x rows 文字の canvas。dot 解像度は (2*cols) x (4*rows)。
    #>
    param(
        [Parameter(Mandatory)][int]$Cols,
        [Parameter(Mandatory)][int]$Rows
    )
    [pscustomobject]@{
        Cols    = $Cols
        Rows    = $Rows
        DotW    = $Cols * 2
        DotH    = $Rows * 4
        # セルごとの dot bit
        Bits    = [int[]]::new($Cols * $Rows)
        # セルごとの色（ANSI SGR 文字列。$null は無色）
        Color   = [string[]]::new($Cols * $Rows)
        # セルごとの上書き文字（ラベル等。$null は Braille を使う）
        Glyph   = [char[]]::new($Cols * $Rows)
        PSTypeName = 'Mortra.Canvas'
    }
}

function Set-MortraDot {
    <#
    .SYNOPSIS
        dot 座標 (x,y) を立てる。範囲外は捨てる。
    #>
    param(
        [Parameter(Mandatory)]$Canvas,
        [Parameter(Mandatory)][int]$X,
        [Parameter(Mandatory)][int]$Y,
        [string]$Color
    )
    if ($X -lt 0 -or $Y -lt 0 -or $X -ge $Canvas.DotW -or $Y -ge $Canvas.DotH) { return }
    $cx = [int][Math]::Floor($X / 2)
    $cy = [int][Math]::Floor($Y / 4)
    $i  = $cy * $Canvas.Cols + $cx
    $Canvas.Bits[$i] = $Canvas.Bits[$i] -bor $script:DOTBIT[$X % 2][$Y % 4]
    if ($Color) { $Canvas.Color[$i] = $Color }
}

function Set-MortraCellText {
    <#
    .SYNOPSIS
        文字セル (col,row) から右へ文字列を焼き込む。Braille より優先される。
    #>
    param(
        [Parameter(Mandatory)]$Canvas,
        [Parameter(Mandatory)][int]$Col,
        [Parameter(Mandatory)][int]$Row,
        [Parameter(Mandatory)][AllowEmptyString()][string]$Text,
        [string]$Color
    )
    if ($Row -lt 0 -or $Row -ge $Canvas.Rows) { return }
    for ($k = 0; $k -lt $Text.Length; $k++) {
        $c = $Col + $k
        if ($c -lt 0 -or $c -ge $Canvas.Cols) { continue }
        $i = $Row * $Canvas.Cols + $c
        $Canvas.Glyph[$i] = $Text[$k]
        if ($Color) { $Canvas.Color[$i] = $Color }
    }
}

function Add-MortraSegment {
    <#
    .SYNOPSIS
        dot 座標の線分。Bresenham。Progress で途中まで描く。
    #>
    param(
        [Parameter(Mandatory)]$Canvas,
        [Parameter(Mandatory)][double]$X0, [Parameter(Mandatory)][double]$Y0,
        [Parameter(Mandatory)][double]$X1, [Parameter(Mandatory)][double]$Y1,
        [string]$Color,
        [double]$Progress = 1.0
    )
    if ($Progress -le 0) { return }
    if ($Progress -lt 1) {
        $X1 = $X0 + ($X1 - $X0) * $Progress
        $Y1 = $Y0 + ($Y1 - $Y0) * $Progress
    }
    $x0 = [int][Math]::Round($X0); $y0 = [int][Math]::Round($Y0)
    $x1 = [int][Math]::Round($X1); $y1 = [int][Math]::Round($Y1)
    $dx = [Math]::Abs($x1 - $x0); $sx = if ($x0 -lt $x1) { 1 } else { -1 }
    $dy = -[Math]::Abs($y1 - $y0); $sy = if ($y0 -lt $y1) { 1 } else { -1 }
    $err = $dx + $dy
    while ($true) {
        Set-MortraDot -Canvas $Canvas -X $x0 -Y $y0 -Color $Color
        if ($x0 -eq $x1 -and $y0 -eq $y1) { break }
        $e2 = 2 * $err
        if ($e2 -ge $dy) { $err += $dy; $x0 += $sx }
        if ($e2 -le $dx) { $err += $dx; $y0 += $sy }
    }
}

function Add-MortraPolyline {
    <#
    .SYNOPSIS
        dot 座標の点列。Progress は列全体の弧長に対する割合。
    #>
    param(
        [Parameter(Mandatory)]$Canvas,
        [Parameter(Mandatory)][double[][]]$Points,
        [string]$Color,
        [double]$Progress = 1.0
    )
    if ($Points.Count -lt 2 -or $Progress -le 0) { return }
    $seg = [double[]]::new($Points.Count - 1)
    $total = 0.0
    for ($i = 0; $i -lt $Points.Count - 1; $i++) {
        $seg[$i] = [Math]::Sqrt(
            [Math]::Pow($Points[$i+1][0] - $Points[$i][0], 2) +
            [Math]::Pow($Points[$i+1][1] - $Points[$i][1], 2))
        $total += $seg[$i]
    }
    if ($total -le 0) { return }
    $want = $total * [Math]::Min($Progress, 1.0)
    $acc = 0.0
    for ($i = 0; $i -lt $seg.Count; $i++) {
        if ($acc + $seg[$i] -le $want) {
            Add-MortraSegment -Canvas $Canvas -X0 $Points[$i][0] -Y0 $Points[$i][1] `
                -X1 $Points[$i+1][0] -Y1 $Points[$i+1][1] -Color $Color
            $acc += $seg[$i]
        } else {
            $p = ($want - $acc) / $seg[$i]
            if ($p -gt 0) {
                Add-MortraSegment -Canvas $Canvas -X0 $Points[$i][0] -Y0 $Points[$i][1] `
                    -X1 $Points[$i+1][0] -Y1 $Points[$i+1][1] -Color $Color -Progress $p
            }
            break
        }
    }
}

function ConvertTo-MortraText {
    <#
    .SYNOPSIS
        canvas を1本の文字列にする。ANSI 付き。末尾に改行は付けない。
    #>
    param(
        [Parameter(Mandatory)]$Canvas,
        [switch]$NoColor
    )
    $sb = [System.Text.StringBuilder]::new($Canvas.Cols * $Canvas.Rows * 2)
    $reset = "$([char]27)[0m"
    for ($r = 0; $r -lt $Canvas.Rows; $r++) {
        $cur = $null
        for ($c = 0; $c -lt $Canvas.Cols; $c++) {
            $i = $r * $Canvas.Cols + $c
            $g = $Canvas.Glyph[$i]
            $ch = if ($g -ne [char]0) { $g } else { [char](0x2800 + $Canvas.Bits[$i]) }
            if (-not $NoColor) {
                $col = $Canvas.Color[$i]
                if ($col -ne $cur) {
                    if ($cur) { [void]$sb.Append($reset) }
                    if ($col) { [void]$sb.Append($col) }
                    $cur = $col
                }
            }
            [void]$sb.Append($ch)
        }
        if ($cur) { [void]$sb.Append($reset) }
        if ($r -lt $Canvas.Rows - 1) { [void]$sb.Append("`n") }
    }
    $sb.ToString()
}

Export-ModuleMember -Function New-MortraCanvas, Set-MortraDot, Set-MortraCellText,
    Add-MortraSegment, Add-MortraPolyline, ConvertTo-MortraText
