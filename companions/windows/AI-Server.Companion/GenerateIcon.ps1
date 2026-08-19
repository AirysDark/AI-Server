Add-Type -AssemblyName System.Drawing

$pngPath = Join-Path $PSScriptRoot 'icon.png'
$icoPath = Join-Path $PSScriptRoot 'icon.ico'

if (-not (Test-Path $pngPath)) {
    throw "Missing icon.png: $pngPath"
}

$bitmap = [System.Drawing.Bitmap]::new($pngPath)
try {
    $size = [Math]::Min($bitmap.Width, $bitmap.Height)
    $square = [System.Drawing.Bitmap]::new(256, 256)
    try {
        $graphics = [System.Drawing.Graphics]::FromImage($square)
        try {
            $graphics.Clear([System.Drawing.Color]::Transparent)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $graphics.DrawImage($bitmap, 0, 0, 256, 256)
        }
        finally {
            $graphics.Dispose()
        }

        $handle = $square.GetHicon()
        try {
            $icon = [System.Drawing.Icon]::FromHandle($handle)
            try {
                $stream = [System.IO.File]::Create($icoPath)
                try { $icon.Save($stream) }
                finally { $stream.Dispose() }
            }
            finally { $icon.Dispose() }
        }
        finally { [System.Runtime.InteropServices.Marshal]::DestroyIcon($handle) }
    }
    finally { $square.Dispose() }
}
finally { $bitmap.Dispose() }
