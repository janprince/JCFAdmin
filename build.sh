#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
echo "--- Static files collected ---"
ls -la staticfiles/ || echo "staticfiles directory not found!"
ls staticfiles/paces/ || echo "paces directory not found in staticfiles!"

python manage.py migrate
