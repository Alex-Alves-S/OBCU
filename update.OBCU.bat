@echo off
cls
:menu
cls
color 0A

date /t
set hora=%time:~0,2%:%time:~3,2%
echo %hora%


echo            MENU DE TAREFAS
echo ===========================================
echo * 1. Comunicacao OBCU                      *
echo * 2. Update All                            *
echo * 3. Set Train Id                          *
echo * 4. Get Train Id                          *
echo * 5. Close                                 *
echo ===========================================

set /p opcao= Escolha uma opcao:
echo ------------------------------------
if %opcao% equ 1 goto opcao1
if %opcao% equ 2 goto opcao2
if %opcao% equ 3 goto opcao3
if %opcao% equ 4 goto opcao4
if %opcao% equ 5 goto opcao5

:opcao1
cls
echo =============================
echo *     COMUNICAO OBCU        *
echo =============================
netsh interface ip set address name="Ethernet" static 192.168.0.221 255.255.255.0 192.168.0.1
ping 192.168.0.190
pause
goto menu

:opcao2
cls
echo =======================
echo *      UPDATE-ALL     *
echo =======================
cd C:/OBS_LOCAL_UPDATE
fab update-all
pause
goto menu

:opcao3
cls
echo ================================
echo *        SET-TRAIN-ID          *
echo ================================
cd C:/OBS_LOCAL_UPDATE
fab set-train-id
pause
goto menu

:opcao4
cls
echo ================================
echo *        GET-TRAIN-ID          *
echo ================================
cd C:/OBS_LOCAL_UPDATE
fab get-train-id
pause
goto menu

:opcao5
cls
exit
