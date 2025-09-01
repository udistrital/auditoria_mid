#!/usr/bin/env bash

set -e
set -u
set -o pipefail
gunicorn api:app --bind 0.0.0.0:$API_PORT
