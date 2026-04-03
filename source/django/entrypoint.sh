#!/bin/sh
set -e

#=============================================================================
# BAIN (Bolls Bible) - Container Startup
#=============================================================================
log_ts() {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
}

log() {
    echo "[$(log_ts)] - [INFO] - $1"
}

log_warn() {
    echo "[$(log_ts)] - [WARN] - $1"
}

log_error() {
    echo "[$(log_ts)] - [ERROR] - $1" >&2
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BAIN (Bolls Bible) - Container Startup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Running as UID: $(id -u), GID: $(id -g)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

#=============================================================================
# Setup Logging Directory (NOT under /static/ to prevent browser access)
#=============================================================================
LOG_DIR="/app/logs"
SEED_LOG="$LOG_DIR/seeding.log"
mkdir -p "$LOG_DIR"
log "Seeding logs will be written to: $SEED_LOG"

#=============================================================================
# Wait for Database
#=============================================================================
if [ "$DATABASE" = "postgres" ]
then
    log "Waiting for postgres..."
    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done
    log "PostgreSQL started"
fi

#=============================================================================
# Database Setup
#=============================================================================
# Create PostgreSQL extensions required for dictionary search
log "Ensuring PostgreSQL extensions..."
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
" 2>/dev/null || log_warn "Could not create extensions"

# Run migrations on every startup (safe - Django handles idempotency)
log "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
log "Collecting static files..."
python manage.py collectstatic --noinput

#=============================================================================
# Data Verification
#=============================================================================
DATA_DIR="/app/data"
log "Checking bundled data files..."
if [ -d "$DATA_DIR/translations" ]; then
    TRANS_COUNT=$(ls -1 "$DATA_DIR/translations"/*.json 2>/dev/null | wc -l)
    log "Found $TRANS_COUNT translation JSON files in $DATA_DIR/translations/"
else
    log_warn "Translation data directory not found at $DATA_DIR/translations/"
fi
if [ -d "$DATA_DIR/dictionaries" ]; then
    DICT_FILES=$(ls -1 "$DATA_DIR/dictionaries"/*.json 2>/dev/null | wc -l)
    log "Found $DICT_FILES dictionary JSON files in $DATA_DIR/dictionaries/"
else
    log_warn "Dictionary data directory not found at $DATA_DIR/dictionaries/"
fi

#=============================================================================
# Seeding Function (runs in background with low priority)
#=============================================================================
run_seeding() {
    log "Starting background seeding process with low priority..."
    echo "[$(log_ts)] - [INFO] - Seeding process started" >> "$SEED_LOG"

    # Run seeding with nice (low CPU priority) and ionice (low I/O priority)
    # nice -n 19 = lowest CPU priority
    # ionice -c 3 = idle I/O class (only runs when disk is idle)
    {
        log "Running Bible seeding..."
        nice -n 19 ionice -c 3 python manage.py seed_bible 2>&1

        log "Running Dictionary seeding..."
        nice -n 19 ionice -c 3 python manage.py seed_dictionary 2>&1

        echo "[$(log_ts)] - [INFO] - Seeding process completed"
    } >> "$SEED_LOG" 2>&1 &

    SEED_PID=$!
    log "Seeding started in background (PID: $SEED_PID). Monitor with: tail -f $SEED_LOG"
}

#=============================================================================
# Bootstrap Superuser (if environment variables provided)
#=============================================================================
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    log "Checking for superuser..."
    SUPERUSER_EXISTS=$(python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bain.settings')
import django
django.setup()
from django.contrib.auth.models import User
print('yes' if User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists() else 'no')
" 2>/dev/null || echo "no")

    if [ "$SUPERUSER_EXISTS" = "no" ]; then
        log "Creating superuser: $DJANGO_SUPERUSER_USERNAME"
        python manage.py createsuperuser --noinput
        log "Superuser created successfully!"
    else
        log "Superuser '$DJANGO_SUPERUSER_USERNAME' already exists. Skipping."
    fi
fi

#=============================================================================
# Start Data Seeding (Background)
#=============================================================================
# Run seeding in background - idempotent commands will skip if data exists
run_seeding

#=============================================================================
# Start Application
#=============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Starting application..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
exec "$@"
