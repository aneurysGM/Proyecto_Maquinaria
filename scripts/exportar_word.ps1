param(
    [Parameter(Mandatory = $true)][string]$DocxPath,
    [Parameter(Mandatory = $true)][string]$PdfPath,
    [string]$NormalizadoPath
)
$ErrorActionPreference = 'Stop'
$entrada = (Resolve-Path -LiteralPath $DocxPath).Path
$salida = [IO.Path]::GetFullPath($PdfPath)
if ($entrada -eq $salida) { throw 'El PDF no puede sobrescribir el DOCX de entrada.' }
if ($NormalizadoPath -and $entrada -eq [IO.Path]::GetFullPath($NormalizadoPath)) {
    throw 'La copia normalizada debe usar otra ruta para conservar el original.'
}
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.AutomationSecurity = 3
$document = $null
try {
    $document = $word.Documents.Open($entrada, $false, $true)
    if ($NormalizadoPath) {
        $document.SaveAs2([IO.Path]::GetFullPath($NormalizadoPath), 16)
    }
    $document.Repaginate()
    $document.ExportAsFixedFormat($salida, 17)
    Write-Output ('Paginas exportadas por Word: ' + $document.ComputeStatistics(2))
} finally {
    if ($null -ne $document) {
        $document.Close(0)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document)
    }
    $word.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}
