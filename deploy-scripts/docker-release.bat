@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ========================================
REM  WHartTest Docker Image Release Script
REM  Commit running containers to images,
REM  then save as tar archives for offline deployment.
REM
REM  Usage: docker-release.bat <version>
REM  Example: docker-release.bat v2.5.2
REM ========================================

set "VERSION=%~1"
if "%VERSION%"=="" (
    echo ERROR: Version argument is required.
    echo Usage: %~nx0 ^<version^>
    echo Example: %~nx0 v2.5.2
    exit /b 1
)

set "SCRIPT_DIR=%~dp0"

echo ========================================
echo  WHartTest Docker Image Release
echo  Version: %VERSION%
echo  Output: %SCRIPT_DIR%
echo ========================================
echo.

REM ========== Container List (maintain here) ==========
REM These map to container_name in docker-compose.yml.
REM Each container is commit-tagged as wharttest-{name}:{VERSION}.
set "CONTAINERS[0]=wharttest-postgres"
set "CONTAINERS[1]=wharttest-redis"
set "CONTAINERS[2]=wharttest-backend"
set "CONTAINERS[3]=wharttest-weixin-plugin-host"
set "CONTAINERS[4]=wharttest-frontend"
set "CONTAINERS[5]=wharttest-mcp"
set "CONTAINERS[6]=wharttest-playwright-mcp"
set "CONTAINERS[7]=wharttest-qdrant"

REM ========== Step 1: docker commit all containers ==========
echo [Step 1/2] Committing running containers ...
echo.

set "INDEX=0"
set "COMMIT_COUNT=0"

:COMMIT_LOOP
call set "CONTAINER=%%CONTAINERS[!INDEX!]%%"
if "!CONTAINER!"=="" goto COMMIT_DONE

set /a NUM=INDEX+1
echo [%NUM%] Committing !CONTAINER! ...
docker commit !CONTAINER! !CONTAINER!:!VERSION!
if !ERRORLEVEL! neq 0 (
    echo "[WARN] Container !CONTAINER! commit failed (may not be running), skipped."
) else (
    set /a COMMIT_COUNT+=1
    echo [OK] !CONTAINER!:!VERSION!
)
echo.

set /a INDEX+=1
goto COMMIT_LOOP
:COMMIT_DONE

if "%COMMIT_COUNT%"=="0" (
    echo [ERROR] No containers committed. Ensure containers are running.
    exit /b 1
)

echo %COMMIT_COUNT% image(s) committed successfully.
echo.

REM ========== Step 2: Save images as tar ==========
echo [Step 2/2] Saving images as tar archives ...
echo.

set "INDEX=0"
set "SAVED_COUNT=0"

:SAVE_LOOP
call set "CONTAINER=%%CONTAINERS[!INDEX!]%%"
if "!CONTAINER!"=="" goto SAVE_DONE

docker save -o "%SCRIPT_DIR%!CONTAINER!-!VERSION!.tar" !CONTAINER!:!VERSION!
if !ERRORLEVEL! equ 0 (
    set /a SAVED_COUNT+=1
    echo [OK] !CONTAINER!-!VERSION!.tar
)

set /a INDEX+=1
goto SAVE_LOOP
:SAVE_DONE

echo.
echo %SAVED_COUNT% tar file(s) saved.
echo.

REM ========== Step 3: Generate .env ==========
echo VERSION=%VERSION% > "%SCRIPT_DIR%.env"
echo [OK] .env generated.

echo.
echo ========================================
echo  Done!
echo  Output directory: %SCRIPT_DIR%
echo.
echo  Offline deployment steps:
echo  1. Copy deploy-scripts to the target machine
echo  2. Run load-images.bat to load all images
echo  3. Run "docker compose up -d" to start
echo ========================================
echo.

endlocal
