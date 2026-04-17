@echo off
REM Training run for the 2026-04-18 ceremony — 108 pairs + existing corpus.
REM Produces models/lora/2026-04-18 and updates the "latest" symlink.
REM Logs: logs/train-ceremony.log

cd /d C:\Projects\svapna
if not exist logs mkdir logs

REM Clear inherited API keys — training doesn't call Claude API, but be safe.
set ANTHROPIC_API_KEY=
set ANTHROPIC_AUTH_TOKEN=

echo. >> logs\train-ceremony.log
echo ================================================================ >> logs\train-ceremony.log
echo [%date% %time%] Training starting... >> logs\train-ceremony.log
echo ================================================================ >> logs\train-ceremony.log

python -u scripts\train_ceremony.py >> logs\train-ceremony.log 2>&1

echo [%date% %time%] Training exited (code %errorlevel%) >> logs\train-ceremony.log
