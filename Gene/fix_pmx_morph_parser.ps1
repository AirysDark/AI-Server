$ErrorActionPreference = 'Stop'

$path = Join-Path $PSScriptRoot 'src\gene_model.cpp'
if (-not (Test-Path $path)) { throw "Cannot find $path" }

$text = Get-Content -Raw -LiteralPath $path
$old = @'
            case 8:
                if (!r.index(idx, materialIndexSize, true)) return fail("bad material morph index " + std::to_string(i));
                for (int n = 0; n < 28; ++n) if (!r.f32(f)) return fail("bad material morph data " + std::to_string(i));
                break;
'@
$new = @'
            case 8: {
                // PMX material morph offset starts with an operation byte:
                // 0 = multiply, 1 = add. It is followed by 28 floats.
                if (!r.index(idx, materialIndexSize, true)) return fail("bad material morph index " + std::to_string(i));
                uint8_t operation{};
                if (!r.u8(operation)) return fail("bad material morph operation " + std::to_string(i));
                if (operation > 1) return fail("invalid material morph operation " + std::to_string(operation) + " at morph " + std::to_string(i));
                for (int n = 0; n < 28; ++n) if (!r.f32(f)) return fail("bad material morph data " + std::to_string(i));
                break;
            }
'@

if (-not $text.Contains($old)) { throw 'Expected material morph parser block was not found; no changes made.' }
$text = $text.Replace($old, $new)
Set-Content -LiteralPath $path -Value $text -NoNewline -Encoding UTF8
Write-Host "Patched: $path"
Write-Host "Material morph operation byte is now consumed correctly."
