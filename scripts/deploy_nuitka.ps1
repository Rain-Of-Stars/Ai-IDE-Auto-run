# PowerShell UTF-8 严格模式
$ErrorActionPreference='Stop'
[Console]::InputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$env:PYTHONIOENCODING = 'utf-8'

# 可选：使用conda环境（按需修改路径）
# $python = "C:/Users/wcx/.conda/envs/use/python.exe"
$python = (Get-Command python).Source

Write-Host "使用 Python: $python"

# Nuitka 打包（需要预先 pip install nuitka ordered-set zstandard)
$args = @(
    "-m", "nuitka",
    "--onefile",
    "--enable-plugin=pyside6",
    "--include-data-dir=assets=assets",
    "--output-dir=dist",
    "main_auto_approve.py"
)

& $python $args

if ($LASTEXITCODE -eq 0) {
    Write-Host "打包完成，产物位于 dist/"
} else {
    Write-Error "打包失败：$LASTEXITCODE"
}

