if (!(Test-Path .venv)) {
    echo ".venv 없음. python 3.12의 venv를 구성합니다."
    py -3.12 -m venv .venv
}

.\.venv\Scripts\Activate

pip install -r requirements.txt

$ApiSetuppath = Join-Path $env:VBOX_MSI_INSTALL_PATH "sdk\installer\python"

if (!(Test-Path $ApiSetuppath)) {
    throw "VirtualBox api setup을 위한 경로를 찾을 수 없습니다."
}

if ($LASTEXITCODE -eq 0) {
    if (Test-Path "./_apisetup") {
        throw "./_apisetup 경로가 이미 존재합니다."
    }
    Copy-Item $ApiSetuppath ./_apisetup -Recurse
    cd ./_apisetup
    python vboxapisetup.py install
    cd ..
    Remove-Item ./_apisetup -Recurse -Force

    echo "프로젝트 구성을 완료했습니다."
}
