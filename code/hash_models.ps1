$ErrorActionPreference = 'Stop'
$files = Get-ChildItem 'C:\Models' -Recurse -Filter *.gguf
foreach ($f in $files) {
    $h = (Get-FileHash $f.FullName -Algorithm SHA256).Hash
    Write-Output ('{0}  {1}' -f $h, $f.FullName)
}
