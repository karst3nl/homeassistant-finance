#!/bin/sh
# Option LOG_LEVEL kommt aus den Add-on-Optionen (siehe config.yaml).
exec uvicorn main:app --host 0.0.0.0 --port 8099 --log-level "${LOG_LEVEL:-info}"
