#!/usr/bin/env bash
# Build do Render (roda a partir da raiz do repositório).
set -o errexit

pip install -r requirements-web.txt
python web/manage.py collectstatic --noinput
