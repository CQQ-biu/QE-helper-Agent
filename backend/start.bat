@echo off
echo Starting QE Helper Backend...
echo.
echo Starting FastAPI server...
start "FastAPI Server" cmd /k "python run.py"
timeout /t 2
echo.
echo Starting Celery Worker...
start "Celery Worker" cmd /k "python run_celery.py"
echo.
echo Backend services started!
echo FastAPI: http://localhost:8000
echo.
pause

