$ErrorActionPreference = 'Stop'
$taskFolder = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if ((Split-Path -Leaf $taskFolder) -ne 'SuperSymmarXL') { throw 'Unexpected delivery folder' }
$revisionFolder = Join-Path $taskFolder 'revision4'
foreach ($required in @('acceptance.json','final_integrity.json')) {
 if (-not (Test-Path -LiteralPath (Join-Path $revisionFolder $required))) { throw "Missing verification $required" }
}
$validated = Get-Content -LiteralPath (Join-Path $revisionFolder 'validated.json') -Raw | ConvertFrom-Json
if ($validated.asphere_A4_to_A6.Count -ne 2) { throw 'A4/A6 validation required' }
$acceptance = Get-Content -LiteralPath (Join-Path $revisionFolder 'acceptance.json') -Raw | ConvertFrom-Json
if ($acceptance.source_sha256 -ne $validated.source_sha256) { throw 'Report source identity mismatch' }
$integrity = Get-Content -LiteralPath (Join-Path $revisionFolder 'final_integrity.json') -Raw | ConvertFrom-Json
foreach ($record in $integrity) {
 if ($record.source_sha256 -ne $validated.source_sha256) { throw 'Integrity source mismatch' }
 if ((Get-FileHash -LiteralPath (Join-Path $revisionFolder $record.file) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $record.sha256) { throw 'Native model changed after validation' }
}
$pairs = @(
 @('models','SuperSymmarXL_150_R4_f5p6.zmx','SuperSymmarXL_150_f5p6_reverse.zmx'),
 @('models','SuperSymmarXL_150_R4_f8.zmx','SuperSymmarXL_150_f8_reverse.zmx'),
 @('models','SuperSymmarXL_150_R4_f22.zmx','SuperSymmarXL_150_f22_reverse.zmx'),
 @('reports','光学性能与制造可能性报告_R4.pdf','光学性能与制造可能性报告.pdf'),
 @('reports','光学性能与制造可能性报告_R4.md','光学性能与制造可能性报告.md'),
 @('analysis','MTF_full_field.png','mtf_comparison.png'),
 @('analysis','section_verified.png','lens_section.png')
)
foreach ($pair in $pairs) {
 $source = Join-Path $revisionFolder $pair[1]
 $destination = Join-Path (Join-Path $taskFolder $pair[0]) $pair[2]
 $archive = Join-Path (Join-Path $taskFolder $pair[0]) 'archive_R3_before_R4'
 $archived = Join-Path $archive $pair[2]
 foreach ($target in @($source,$destination,$archive,$archived)) {
  $resolvedTarget = [IO.Path]::GetFullPath($target)
  if (-not $resolvedTarget.StartsWith($taskFolder + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw "Target outside delivery folder: $resolvedTarget" }
 }
 if (-not (Test-Path -LiteralPath $source)) { throw "Missing source $source" }
 if (Test-Path -LiteralPath $archived) { throw "Already promoted: $archived" }
}
foreach ($pair in $pairs) {
 $source = Join-Path $revisionFolder $pair[1]
 $destination = Join-Path (Join-Path $taskFolder $pair[0]) $pair[2]
 if (Test-Path -LiteralPath $destination) {
  $archive = Join-Path (Join-Path $taskFolder $pair[0]) 'archive_R3_before_R4'
  New-Item -ItemType Directory -Path $archive -Force | Out-Null
  Move-Item -LiteralPath $destination -Destination (Join-Path $archive $pair[2])
 }
 Copy-Item -LiteralPath $source -Destination $destination
 if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) { throw 'Copy hash mismatch' }
}
Copy-Item -LiteralPath (Join-Path $taskFolder 'README.md') -Destination (Join-Path $revisionFolder 'README_before_R4.md')
Copy-Item -LiteralPath (Join-Path $revisionFolder 'README_R4.md') -Destination (Join-Path $taskFolder 'README.md')
Write-Output 'R4 A6 delivery verified; R3 preserved.'
