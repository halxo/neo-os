@echo off
setlocal enabledelayedexpansion

title NeoOS (Gentoo + OpenRC) - Docker & VirtualBox Setup

set "WORK_DIR=%~dp0"
set "ISO_DIR=%WORK_DIR%out"
set "ISO_FILE=%ISO_DIR%\neoos-gentoo-1.0-x86_64.iso"
set "ISO_URL=https://github.com/halxo/neo-os/releases/download/v1.0-gentoo/neoos-gentoo-1.0-x86_64.iso"
set "REPO_ZIP_URL=https://github.com/halxo/neo-os/archive/refs/heads/main.zip"
set "VM_NAME=NeoOS-Gentoo"
set "VM_RAM=4096"
set "VM_CPUS=4"
set "VM_VRAM=128"
set "VM_DISK_MB=51200"
set "SHA_URL=https://github.com/halxo/neo-os/releases/download/v1.0-gentoo/neoos-gentoo-1.0-x86_64.iso.sha256"

echo ============================================================
echo   NeoOS (Gentoo + OpenRC) - VirtualBox ^& Docker Launcher
echo ============================================================
echo.

if not exist "%ISO_DIR%" mkdir "%ISO_DIR%"

if exist "%ISO_FILE%" (
    set "REMOTE_SHA="
    set "LOCAL_SHA="
    for /f "tokens=1" %%S in ('curl.exe -fsSL "%SHA_URL%" 2^>nul') do set "REMOTE_SHA=%%S"
    if defined REMOTE_SHA (
        for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 -LiteralPath '%ISO_FILE%').Hash.ToLower()" 2^>nul`) do set "LOCAL_SHA=%%H"
        if defined LOCAL_SHA if /i not "!LOCAL_SHA!"=="!REMOTE_SHA!" (
            echo [UPDATE] A newer NeoOS ISO release is available on GitHub. Updating local ISO...
            del /f /q "%ISO_FILE%"
            goto :download_iso
        )
    )
    echo [OK] Found up-to-date ISO: "%ISO_FILE%"
    goto :setup_vbox
)

echo Choose how to obtain neoos-gentoo-1.0-x86_64.iso:
echo   [1] Download premade ISO from GitHub Releases (Fastest)
echo   [2] Build ISO locally using premade Docker setup (docker compose)
echo.
set /p "CHOICE=Enter choice [1 or 2, default=1]: "
if "%CHOICE%"=="" set "CHOICE=1"

if "%CHOICE%"=="2" goto :build_docker

:download_iso
echo.
echo ==^> Downloading NeoOS Gentoo OpenRC ISO...
echo     %ISO_URL%
curl.exe -fL --progress-bar "%ISO_URL%" -o "%ISO_FILE%"
if errorlevel 1 (
    if exist "%ISO_FILE%" del /f /q "%ISO_FILE%"
    echo.
    echo [WARN] Direct ISO download failed ^(release may still be building^).
    set /p "FALLBACK=Fall back to local Docker build now? [Y/n]: "
    if /i "!FALLBACK!"=="n" exit /b 1
    goto :build_docker
)
goto :setup_vbox

:build_docker
echo.
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not installed or not in PATH.
    echo         Install Docker Desktop: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

set "COMPOSE_DIR=%WORK_DIR%"
if not exist "%COMPOSE_DIR%docker-compose.yml" (
    echo ==^> docker-compose.yml not found next to .bat; fetching NeoOS Docker setup...
    set "SRC_ZIP=%WORK_DIR%neo-os-main.zip"
    curl.exe -fL --progress-bar "%REPO_ZIP_URL%" -o "!SRC_ZIP!"
    if errorlevel 1 (
        echo [ERROR] Failed to download NeoOS repository archive.
        pause
        exit /b 1
    )
    tar.exe -xf "!SRC_ZIP!" -C "%WORK_DIR%"
    del /f /q "!SRC_ZIP!"
    set "COMPOSE_DIR=%WORK_DIR%neo-os-main\"
)

echo ==^> Building NeoOS Gentoo OpenRC ISO via Docker Compose...
pushd "%COMPOSE_DIR%"
docker compose build build-iso && docker compose run --rm build-iso
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" (
    echo [ERROR] Docker ISO build failed ^(exit code %RC%^).
    pause
    exit /b %RC%
)
if not "%COMPOSE_DIR%"=="%WORK_DIR%" (
    if exist "%COMPOSE_DIR%out\neoos-gentoo-1.0-x86_64.iso" (
        copy /y "%COMPOSE_DIR%out\neoos-gentoo-1.0-x86_64.iso" "%ISO_FILE%" >nul
    )
)

:setup_vbox
echo.
set "VBOXMANAGE="
where VBoxManage.exe >nul 2>&1
if not errorlevel 1 set "VBOXMANAGE=VBoxManage.exe"
if "%VBOXMANAGE%"=="" if exist "%ProgramFiles%\Oracle\VirtualBox\VBoxManage.exe" set "VBOXMANAGE=%ProgramFiles%\Oracle\VirtualBox\VBoxManage.exe"
if "%VBOXMANAGE%"=="" if exist "%ProgramFiles(x86)%\Oracle\VirtualBox\VBoxManage.exe" set "VBOXMANAGE=%ProgramFiles(x86)%\Oracle\VirtualBox\VBoxManage.exe"

if "%VBOXMANAGE%"=="" (
    echo [WARN] VirtualBox ^(VBoxManage.exe^) was not found.
    echo        Your ISO is ready at: "%ISO_FILE%"
    echo        Install VirtualBox from https://www.virtualbox.org/ and attach the ISO manually.
    pause
    exit /b 0
)

echo ==^> Configuring VirtualBox VM "%VM_NAME%"...
"%VBOXMANAGE%" showvminfo "%VM_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] VM "%VM_NAME%" already exists. Updating DVD ISO attachment and starting...
    "%VBOXMANAGE%" controlvm "%VM_NAME%" poweroff >nul 2>&1
    timeout /t 2 /nobreak >nul 2>&1
    "%VBOXMANAGE%" storageattach "%VM_NAME%" --storagectl "IDE" --port 0 --device 0 --type dvddrive --medium "%ISO_FILE%"
    goto :start_vm
)

set "VM_DISK=%USERPROFILE%\VirtualBox VMs\%VM_NAME%\%VM_NAME%.vdi"
"%VBOXMANAGE%" createvm --name "%VM_NAME%" --ostype "Gentoo_64" --register
"%VBOXMANAGE%" modifyvm "%VM_NAME%" --memory %VM_RAM% --cpus %VM_CPUS% --vram %VM_VRAM% --graphicscontroller vmsvga --firmware efi --nic1 nat --audio-enabled on --usb-xhci on --boot1 dvd --boot2 disk
"%VBOXMANAGE%" createmedium disk --filename "%VM_DISK%" --size %VM_DISK_MB% --format VDI
"%VBOXMANAGE%" storagectl "%VM_NAME%" --name "SATA" --add sata --controller IntelAhci
"%VBOXMANAGE%" storageattach "%VM_NAME%" --storagectl "SATA" --port 0 --device 0 --type hdd --medium "%VM_DISK%"
"%VBOXMANAGE%" storagectl "%VM_NAME%" --name "IDE" --add ide
"%VBOXMANAGE%" storageattach "%VM_NAME%" --storagectl "IDE" --port 0 --device 0 --type dvddrive --medium "%ISO_FILE%"

:start_vm
echo.
echo ==^> Launching "%VM_NAME%" in VirtualBox...
"%VBOXMANAGE%" startvm "%VM_NAME%" --type gui
if errorlevel 1 (
    echo [ERROR] Failed to start VirtualBox VM.
    pause
    exit /b 1
)

echo.
echo [DONE] NeoOS Gentoo OpenRC is booting in VirtualBox!
echo        Live credentials: user=neo, password=neo
pause
exit /b 0
