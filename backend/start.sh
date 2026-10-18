#!/bin/bash
echo "Starting QE Helper Backend..."
echo ""
echo "Starting FastAPI server..."
python run.py &
FASTAPI_PID=$!
sleep 2
echo ""
echo "Starting Celery Worker..."
python run_celery.py &
CELERY_PID=$!
echo ""
echo "Backend services started!"
echo "FastAPI: http://localhost:8000"
echo "FastAPI PID: $FASTAPI_PID"
echo "Celery PID: $CELERY_PID"
echo ""
echo "Press Ctrl+C to stop all services"
trap "kill $FASTAPI_PID $CELERY_PID; exit" INT
wait

