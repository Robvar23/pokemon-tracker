@echo off
rem Sends a test message to Discord / email using config.json.
cd /d "%~dp0"
call run.bat --test
