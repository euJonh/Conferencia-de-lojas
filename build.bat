@echo off
rem Gera dist\ConferenciaLojas.exe (com o ícone da pena) e o instalador
rem instalador\Instalar_ConferenciaLojas_<versão>.exe, que leva o .exe, o lojas.txt e o modelo.
cd /d "%~dp0"

python -m pip install -r requirements.txt || goto erro
python -m PyInstaller --onefile --windowed --clean --noconfirm --name ConferenciaLojas ^
    --icon icone.ico --add-data "icone.ico;." conferencia.py || goto erro

if exist lojas.txt copy /Y lojas.txt dist\lojas.txt >nul
if exist "PLANILHA DE PEDIDOS.xlsx" copy /Y "PLANILHA DE PEDIDOS.xlsx" "dist\PLANILHA DE PEDIDOS.xlsx" >nul

rem Inno Setup 6: instalado por usuário (winget) ou para todos.
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo.
    echo Inno Setup 6 nao encontrado; o instalador nao foi gerado.
    echo Instale com: winget install --id JRSoftware.InnoSetup -e
    goto fim
)
"%ISCC%" /Q instalador.iss || goto erro

:fim
echo.
echo Pronto: dist\ConferenciaLojas.exe
if exist instalador echo Instalador: pasta instalador
pause
exit /b 0

:erro
echo.
echo Falha ao gerar o executavel ou o instalador.
pause
exit /b 1
