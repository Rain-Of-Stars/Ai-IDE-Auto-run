$ErrorActionPreference = 'Stop'

# 设置PowerShell与控制台UTF-8，避免中文乱码
[Console]::InputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$env:PYTHONIOENCODING = 'utf-8'
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'

Write-Host 'OK: UTF-8 configured'

# 使用指定的conda环境运行（如需更换请修改以下路径）
$python = 'C:/Users/wcx/.conda/envs/use/python.exe'

if (-not (Test-Path $python)) {
  Write-Warning "未找到指定Python: $python，改用PATH中的python。"
  $python = 'python'
}

# 运行主程序（在项目根目录执行）
& $python 'main_auto_approve.py'

