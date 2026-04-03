# Bain (Bolls Bible) - Docker Deployment

A self-hosted Bible application with 144 translations, 4.2M+ verses, and dictionary support.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/freedbygrace/bain.git
cd bain

# Generate secrets
export SECRET_KEY=$(openssl rand -base64 64)
export POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Start the stack
docker compose up -d
```

Access the application at **http://localhost:8380**

## Default Login

| Field | Value |
|-------|-------|
| **Username** | `admin` |
| **Password** | `admin` |

> ⚠️ **Change these credentials in production** via `DJANGO_SUPERUSER_USERNAME` and `DJANGO_SUPERUSER_PASSWORD` environment variables.

## Features

- **144 Bible Translations** - All data is baked into the Docker image
- **4.2+ Million Verses** - Automatically seeded on first startup
- **3 Dictionaries** - BDBT, RUSD, SCGES
- **Idempotent Seeding** - Restarts don't re-import existing data
- **Resource Efficient** - Background seeding with low CPU/IO priority
- **Any UID/GID Support** - Works with any host user permissions

## Configuration

Create a `.env` file or export environment variables:

```bash
# Secrets (REQUIRED - generate with openssl)
export SECRET_KEY=$(openssl rand -base64 64)
export POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Host port mapping (optional, default: 8380)
BAIN_PORT=8380

# Data persistence location (optional, defaults shown)
STACK_BINDMOUNTROOT=/custom/docker/stacks
STACK_NAME=stk-bain-00001

# User/Group IDs - match your host user (optional)
PUID=1000
PGID=1000
```

## Compose Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | **Production** - Uses pre-built images from DockerHub |
| `docker-compose.build.yml` | **Development** - Builds images locally from source |

### Production Deployment (Default)

```bash
docker compose up -d
```

### Local Build (Development)

```bash
docker compose -f docker-compose.build.yml up -d --build
```

### Build and Push Images

```bash
export DOCKER_USER="your-username"
export DOCKER_PAT="your-personal-access-token"
./deploy.sh build
./deploy.sh push
```

## Architecture

| Service | Description | Port |
|---------|-------------|------|
| **Proxy** | Nginx reverse proxy | 8380 (external) |
| **App** | Django REST API | 8000 (internal) |
| **Web** | Imba Node.js frontend | 3000 (internal) |
| **DB** | PostgreSQL + pgvector | 5432 (internal) |

## Data Volumes

| Path | Purpose |
|------|---------|
| `${STACK_BINDMOUNTROOT}/${STACK_NAME}/DB` | PostgreSQL data |
| `${STACK_BINDMOUNTROOT}/${STACK_NAME}/App/Static` | Django static files |
| `${STACK_BINDMOUNTROOT}/${STACK_NAME}/App/Logs` | Seeding logs |
| `${STACK_BINDMOUNTROOT}/${STACK_NAME}/Web/Build` | Frontend build output |

## Monitoring

Check seeding progress:

```bash
# View seeding log
docker exec BAIN-APP-00001 cat /app/logs/seeding.log

# Check verse count
docker exec BAIN-DB-00001 psql -U bain -d bain -c "SELECT COUNT(*) FROM bolls_verses;"
```

## Resource Limits

The App container is configured with:
- **CPU**: 1.0 cores max (configurable via `BAIN_APP_CPU_LIMIT`)
- **Memory**: 2GB max (configurable via `BAIN_APP_MEM_LIMIT`)
- **Seeding**: Runs with `nice -n 19` and `ionice -c 3` (lowest priority)

## Troubleshooting

### Force Re-seed

```bash
docker exec BAIN-APP-00001 python manage.py seed_bible --force
docker exec BAIN-APP-00001 python manage.py seed_dictionary --force
```

### Reset Everything

```bash
docker compose down -v
sudo rm -rf "${STACK_BINDMOUNTROOT}/${STACK_NAME}"/*
docker compose up -d
```

## API Endpoints

- `GET /get-text/{translation}/{book}/{chapter}/` - Get chapter verses
- `GET /get-books/` - List all books
- `GET /search/` - Full-text search
- `GET /api/` - API documentation

## Credits

Based on [Bolls Bible](https://github.com/nickspaargaren/bain) by Boguslavv.

## License

See [LICENSE](source/LICENSE) for details.

