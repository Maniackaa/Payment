#!/bin/sh

# run a worker :)
celery -A backend_payment worker --loglevel=info --concurrency 1 -E