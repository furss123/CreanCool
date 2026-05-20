param(
    [Parameter(Mandatory = $true)]
    [string]$GitHubUser,
    [Parameter(Mandatory = $false)]
    [string]$RepoName = "CreanCool"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

function Find-Git {
    $candidates = @(
        "git",
        "${env:ProgramFiles}\Git\bin\git.exe",
        "${env:ProgramFiles}\Git\cmd\git.exe"
    )
    foreach ($c in $candidates) {
        if (Get-Command $c -ErrorAction SilentlyContinue) {
            return (Get-Command $c).Source
        }
        if (Test-Path $c) { return $c }
    }
    return $null
}

$git = Find-Git
if (-not $git) {
    Write-Host "Git이 설치되어 있지 않습니다." -ForegroundColor Red
    Write-Host "https://git-scm.com/download/win 설치 후 PowerShell을 다시 실행하세요."
    exit 1
}

$remote = "https://github.com/$GitHubUser/$RepoName.git"
Write-Host "Repository: $remote"

if (-not (Test-Path ".git")) {
    & $git init
}
& $git add .
& $git status
$msg = "Update CreanCool teacher workflow app"
& $git commit -m $msg 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "커밋할 변경이 없거나 이미 커밋됨" -ForegroundColor Yellow
}

& $git branch -M main 2>$null
$hasOrigin = & $git remote 2>$null | Select-String -Pattern "^origin$"
if (-not $hasOrigin) {
    & $git remote add origin $remote
} else {
    & $git remote set-url origin $remote
}

Write-Host ""
Write-Host "다음 명령으로 푸시합니다 (GitHub 로그인 필요):" -ForegroundColor Cyan
Write-Host "  git push -u origin main"
& $git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "완료! GitHub Pages: https://$GitHubUser.github.io/$RepoName/" -ForegroundColor Green
    Write-Host "Streamlit 배포: https://share.streamlit.io → New app → $GitHubUser/$RepoName"
}
