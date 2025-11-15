#!/bin/bash

cd eventroop_backend

echo "Running migrations..."

pip install -r requirements.txt
python manage.py migrate
python manage.py create_default_groups

echo "Starting server..."
gunicorn eventroop_backend.wsgi:application --bind 0.0.0.0:$PORT
#!/bin/bash
set -e



