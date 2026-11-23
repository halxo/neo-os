@echo off
setlocal enabledelayedexpansion

title NeoOS (Gentoo + OpenRC) - Docker & VirtualBox Setup

set "ISO_DIR=%~dp0out"
set "ISO_FILE=%ISO_DIR%\neoos-gentoo-1.0-x86_64.iso"
set "ISO_URL=https://github.com/halxo/neo-os/releases/download/v1.0-gentoo/neoos-gentoo-1.0-x86_64.iso"
set "VM_NAME=NeoOS-Gentoo"
set "VM_RAM=4096"
set "VM_CPUS=4"
set "VM_VRAM=128"
set "VM_DISK_MB=32768"

echo ============================================================
echo   NeoOS (Gentoo + OpenRC) - VirtualBox ^& Docker Launcher
echo ============================================================
echo.

if not exist "%ISO_DIR%" mkdir "%ISO_DIR%"

if exist "%ISO_FILE%" (
    echo [OK] Found existing ISO: "%ISO_FILE%"
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
    echo [ERROR] Download failed. Check your internet connection or try Option 2 ^(Docker build^).
    pause
    exit /b 1
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
echo ==^> Building NeoOS Gentoo OpenRC ISO via Docker Compose...
pushd "%~dp0"
docker compose run --rm build-iso
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" (
    echo [ERROR] Docker ISO build failed ^(exit code %RC%^).
    pause
    exit /b %RC%
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
