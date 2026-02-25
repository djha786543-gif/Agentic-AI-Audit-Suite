$replacements = @{
    'ðŸš'  = '🚀'
    'ðŸ“š' = '📚'
    'ðŸ”'  = '🔍'
    'â€”'  = '—'
    'Â·'   = '·'
    'â„¢'  = '™'
    'Â'    = ''
}
$files = Get-ChildItem -Recurse -Include *.html, *.js, *.css, *.json
foreach ($file in $files) {
    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
    $originalContent = $content
    foreach ($bad in $replacements.Keys) {
        $content = $content.Replace($bad, $replacements[$bad])
    }
    if ($content -ne $originalContent) {
        $content | Out-File -FilePath $file.FullName -Encoding utf8
        Write-Host "Cleaned: $($file.Name)" -ForegroundColor Green
    }
}
Write-Host "Scrubbing complete!" -ForegroundColor Cyan
