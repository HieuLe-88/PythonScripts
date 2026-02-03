param(
    [Parameter(Mandatory=$true)][string]$Folder,
    [Parameter(Mandatory=$false)][string]$Output = "merged_output.mp4",
    [Parameter(Mandatory=$false)][string]$Reference
)

if(-not (Test-Path $Folder)){
    Write-Error "Folder not found: $Folder"
    exit 1
}

$files = Get-ChildItem -Path $Folder -Filter *.mp4 -File | Sort-Object Name | Select-Object -ExpandProperty FullName
if(-not $files -or $files.Count -eq 0){
    Write-Error "No .mp4 files found in folder: $Folder"
    exit 1
}

if($Reference){
    if(-not (Test-Path $Reference)){
        Write-Error "Reference not found: $Reference"
        exit 1
    }
} else {
    $Reference = $files[0]
}

# Build list of inputs excluding the chosen reference (keep order by name)
$inputs = $files | Where-Object { $_ -ne $Reference }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$mergeScript = Join-Path $scriptDir 'merge_videos.ps1'
if(-not (Test-Path $mergeScript)){
    Write-Error "merge_videos.ps1 not found in script directory: $scriptDir"
    exit 1
}

Write-Host "Reference: $Reference"
Write-Host "Merging files (in name order):"
$files | ForEach-Object { Write-Host "  $_" }

& "$mergeScript" -Reference $Reference -Output $Output -Inputs $inputs
