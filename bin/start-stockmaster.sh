#!/bin/bash
cd /home/deploy/stockmaster
source venv/bin/activate
killall gunicorn 2>/dev/null
nohup gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 > /home/deploy/stockmaster/logs/gunicorn.log 2>&1 &
