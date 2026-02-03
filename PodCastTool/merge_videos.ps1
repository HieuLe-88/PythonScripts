param(
    [Parameter(Mandatory=$true)][string]$Reference,
    [Parameter(Mandatory=$true)][string]$Output,
    [Parameter(Mandatory=$true)][string[]]$Inputs
)

function Check-Dependency([string]$cmd){
    $p = Get-Command $cmd -ErrorAction SilentlyContinue
    if(-not $p){ Write-Error "$cmd not found in PATH. Install FFmpeg and ensure ffmpeg/ffprobe are available."; exit 1 }
}

Check-Dependency ffprobe
Check-Dependency ffmpeg

Write-Host "Probing reference video: $Reference"
$json = & ffprobe -v quiet -print_format json -show_streams -show_format -- "$Reference" | ConvertFrom-Json
$v = $json.streams | Where-Object { $_.codec_type -eq 'video' } | Select-Object -First 1
$a = $json.streams | Where-Object { $_.codec_type -eq 'audio' } | Select-Object -First 1

if(-not $v){ Write-Error "No video stream found in reference"; exit 1 }

$fps = 0
try{ $fps = [double](Invoke-Expression $v.avg_frame_rate) } catch { $fps = 30 }
$width = $v.width
$height = $v.height
$ar = "${width}:${height}"
$audio_rate = if($a){ [int]$a.sample_rate } else {44100}
$channels = if($a){ [int]$a.channels } else {2}

Write-Host "Target -> width:$width height:$height fps:$fps audio_rate:$audio_rate channels:$channels"

$cwd = (Get-Location).Path
$fixed = @()

function Fix-File([string]$inFile){
    $safeName = [IO.Path]::GetFileName($inFile)
    $outName = Join-Path $cwd ("fixed_" + $safeName)
    Write-Host "Re-encoding: $inFile -> $outName"
    $vf = "fps=$fps,scale=${width}:${height}:force_original_aspect_ratio=decrease,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2"
    $args = @(
        '-y','-i',$inFile,
        '-vf',$vf,
        '-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',
        '-c:a','aac','-b:a','128k','-ar',$audio_rate,'-ac',$channels,$outName
    )
    Write-Host ('ffmpeg ' + ($args -join ' '))
    & ffmpeg @args
    if($LASTEXITCODE -ne 0){ Write-Warning "ffmpeg returned non-zero exit code for $inFile" }
    return $outName
}

# Re-encode reference and all inputs to ensure exact parity
$fixed += Fix-File $Reference
foreach($f in $Inputs){
    if(-not (Test-Path $f)){ Write-Warning "Input not found: $f"; continue }
    $fixed += Fix-File $f
}

# Create concat list
$listPath = Join-Path $cwd 'merge_list.txt'
"" | Out-File -FilePath $listPath -Encoding ascii
foreach($p in $fixed){
    "file '$p'" | Out-File -FilePath $listPath -Append -Encoding ascii
}

Write-Host "Concatenating into $Output (attempting stream copy)"
& ffmpeg -y -f concat -safe 0 -i "$listPath" -c copy "$Output"
if($LASTEXITCODE -ne 0){
    Write-Warning "Stream-copy concat failed; falling back to re-encode concat"
    & ffmpeg -y -f concat -safe 0 -i "$listPath" -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -c:a aac -b:a 128k "$Output"
}

Write-Host "Done. Output: $Output"
