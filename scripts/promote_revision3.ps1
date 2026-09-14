$ErrorActionPreference = 'Stop'
$taskFolder = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$r3Folder = Join-Path $taskFolder 'revision3'
if (-not (Test-Path -LiteralPath (Join-Path $r3Folder 'acceptance.json'))) { throw 'Validated report is required.' }
$pairs = @(
 @('models', 'SuperSymmarXL_150_R3_f5p6.zmx', 'SuperSymmarXL_150_f5p6_reverse.zmx'),
 @('models', 'SuperSymmarXL_150_R3_f8.zmx', 'SuperSymmarXL_150_f8_reverse.zmx'),
 @('models', 'SuperSymmarXL_150_R3_f22.zmx', 'SuperSymmarXL_150_f22_reverse.zmx'),
 @('reports', '光学性能与制造可能性报告_R3.pdf', '光学性能与制造可能性报告.pdf'),
 @('reports', '光学性能与制造可能性报告_R3.md', '光学性能与制造可能性报告.md'),
 @('analysis', 'MTF_full_field.png', 'mtf_comparison.png'),
 @('analysis', 'section_verified.png', 'lens_section.png')
)
foreach ($pair in $pairs) {
 $source = Join-Path $r3Folder $pair[1]
 if (-not (Test-Path -LiteralPath $source)) { throw "Missing source $source" }
 $destination = Join-Path (Join-Path $taskFolder $pair[0]) $pair[2]
 if (Test-Path -LiteralPath $destination) {
  $archive = Join-Path (Join-Path $taskFolder $pair[0]) 'archive_R2_before_R3'
  New-Item -ItemType Directory -Path $archive -Force | Out-Null
  $archived = Join-Path $archive $pair[2]
  if (Test-Path -LiteralPath $archived) { throw "Already promoted: $archived" }
  Move-Item -LiteralPath $destination -Destination $archived
 }
 Copy-Item -LiteralPath $source -Destination $destination
 if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) { throw 'Copy hash mismatch' }
}
foreach ($oldName in @('光学性能报告.pdf','光学性能报告.md','生产可能性报告.pdf','生产可能性报告.md')) {
 $oldReport = Join-Path (Join-Path $taskFolder 'reports') $oldName
 if (Test-Path -LiteralPath $oldReport) {
  $archive = Join-Path (Join-Path $taskFolder 'reports') 'archive_R2_before_R3'
  New-Item -ItemType Directory -Path $archive -Force | Out-Null
  Move-Item -LiteralPath $oldReport -Destination (Join-Path $archive $oldName)
 }
}
Copy-Item -LiteralPath (Join-Path $taskFolder 'README.md') -Destination (Join-Path $r3Folder 'README_before_R3.md')
Copy-Item -LiteralPath (Join-Path $r3Folder 'README_R3.md') -Destination (Join-Path $taskFolder 'README.md')
Write-Output 'R3 delivery copies hash verified; R2 preserved.'
