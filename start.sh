#!/bin/bash
uvicorn main:app --host 0.0.0.0 --port 8000 &
sleep 3
python bot.py
