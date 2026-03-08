#!/bin/sh
if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."
    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done
    echo "PostgreSQL started"
fi

# Create PostgreSQL extensions required for dictionary search
echo "Ensuring PostgreSQL extensions..."
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bain.settings')
import django
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')
    cursor.execute('CREATE EXTENSION IF NOT EXISTS unaccent;')
print('Extensions ready: pg_trgm, unaccent')
" 2>/dev/null || echo "Warning: Could not create extensions"

# Run migrations on every startup (safe - Django handles idempotency)
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Seed Bible data if database is empty
# Check if YLT translation exists (indicates seeding was done)
VERSE_COUNT=$(python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bain.settings')
import django
django.setup()
from bolls.models import Verses
print(Verses.objects.filter(translation='YLT').count())
" 2>/dev/null || echo "0")

if [ "$VERSE_COUNT" = "0" ] || [ -z "$VERSE_COUNT" ]; then
    echo "Database appears empty. Seeding Bible data (ASV, BSB, ChiSB, KJV, TR, WLC, YLT)..."
    python manage.py seed_bible
    echo "Bible data seeding complete!"
else
    echo "Bible data already present (YLT: $VERSE_COUNT verses). Skipping seed."
fi

# Seed dictionary data if database is empty
DICT_COUNT=$(python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bain.settings')
import django
django.setup()
from bolls.models import Dictionary
print(Dictionary.objects.count())
" 2>/dev/null || echo "0")

if [ "$DICT_COUNT" = "0" ] || [ -z "$DICT_COUNT" ]; then
    echo "Dictionary data not found. Seeding dictionaries (BDBT, RUSD, SCGES)..."
    python manage.py seed_dictionary
    echo "Dictionary seeding complete!"
else
    echo "Dictionary data already present ($DICT_COUNT entries). Skipping seed."
fi

# Bootstrap superuser from environment variables if provided
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Checking for superuser..."
    SUPERUSER_EXISTS=$(python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bain.settings')
import django
django.setup()
from django.contrib.auth.models import User
print('yes' if User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists() else 'no')
" 2>/dev/null || echo "no")

    if [ "$SUPERUSER_EXISTS" = "no" ]; then
        echo "Creating superuser: $DJANGO_SUPERUSER_USERNAME"
        python manage.py createsuperuser --noinput
        echo "Superuser created successfully!"
    else
        echo "Superuser '$DJANGO_SUPERUSER_USERNAME' already exists. Skipping."
    fi
fi

exec "$@"
