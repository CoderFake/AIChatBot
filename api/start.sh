#!/bin/bash
set -e

if [ "${ENV}" = "production" ] || [ "${ENV}" = "prod" ]; then
	echo "Starting in Production Mode..."
	exec gunicorn main:app \
		--bind=0.0.0.0:8000 \
		--workers=${WORKERS:-4} \
		--worker-class=uvicorn.workers.UvicornWorker \
		--max-requests=${MAX_REQUESTS:-1000} \
		--max-requests-jitter=${MAX_REQUESTS_JITTER:-100} \
		--timeout=${TIMEOUT:-120} \
		--graceful-timeout=${GRACEFUL_TIMEOUT:-60} \
		--log-level=${LOG_LEVEL:-info}
else
	echo "Starting in Development Mode..."
	exec uvicorn main:app --host=0.0.0.0 --port=8000 --reload --log-level=debug
fi 