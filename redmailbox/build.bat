@echo off
chcp 65001 >nul
setlocal

echo === 빨간우체통 PyInstaller 빌드 ===

REM 1) 의존성 설치 확인
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [실패] 의존성 설치 실패
    exit /b 1
)

REM 2) 에셋 PNG/ICO 생성 (PIL 사용)
python generate_assets.py
if errorlevel 1 (
    echo [실패] 에셋 생성 실패
    exit /b 1
)

REM 3) PyInstaller 단일 파일 빌드
pyinstaller --noconfirm --clean ^
  --onefile --windowed --name RedMailbox ^
  --icon assets\mailbox.ico ^
  --add-data "assets;assets" ^
  --hidden-import PIL._tkinter_finder ^
  redmailbox.py
if errorlevel 1 (
    echo [실패] PyInstaller 빌드 실패
    exit /b 1
)

echo.
echo === 빌드 완료 ===
echo 결과: dist\RedMailbox.exe
echo 크기:
dir dist\RedMailbox.exe | findstr "RedMailbox"
endlocal
