param(
    [Parameter(Mandatory=$true)][string]$InputPng,
    [Parameter(Mandatory=$true)][string]$OutputIco
)

$png = [System.IO.File]::ReadAllBytes($InputPng)
if ($png.Length -lt 24 -or $png[0] -ne 0x89 -or $png[1] -ne 0x50 -or $png[2] -ne 0x4E -or $png[3] -ne 0x47) {
    throw "Input is not a valid PNG file."
}

$width = ($png[16] -shl 24) -bor ($png[17] -shl 16) -bor ($png[18] -shl 8) -bor $png[19]
$height = ($png[20] -shl 24) -bor ($png[21] -shl 16) -bor ($png[22] -shl 8) -bor $png[23]
if ($width -le 0 -or $height -le 0) { throw "PNG dimensions could not be read." }

$w = if ($width -ge 256) { 0 } else { [byte]$width }
$h = if ($height -ge 256) { 0 } else { [byte]$height }

$stream = New-Object System.IO.MemoryStream
$writer = New-Object System.IO.BinaryWriter($stream)
$writer.Write([UInt16]0)
$writer.Write([UInt16]1)
$writer.Write([UInt16]1)
$writer.Write([byte]$w)
$writer.Write([byte]$h)
$writer.Write([byte]0)
$writer.Write([byte]0)
$writer.Write([UInt16]1)
$writer.Write([UInt16]32)
$writer.Write([UInt32]$png.Length)
$writer.Write([UInt32]22)
$writer.Write($png)
$writer.Flush()
[System.IO.File]::WriteAllBytes($OutputIco, $stream.ToArray())
$writer.Dispose()
$stream.Dispose()
