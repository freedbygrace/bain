# Bain (Bolls Bible) - Docker Deployment

A self-hosted Bible application with 144 translations, 4.2M+ verses, and dictionary support.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/freedbygrace/bain.git
cd bain

# Start the stack
docker compose up -d
```

Access the application at **http://localhost:8380**

## Features

- **144 Bible Translations** - All data is baked into the Docker image
- **4.2+ Million Verses** - Automatically seeded on first startup
- **3 Dictionaries** - BDBT, RUSD, SCGES
- **Idempotent Seeding** - Restarts don't re-import existing data
- **Resource Efficient** - Background seeding with low CPU/IO priority
- **Any UID/GID Support** - Works with any host user permissions

## Configuration

Create a `.env` file (optional):

```bash
# Host port mapping
PROXY_HTTP_PORT=8380

# User/Group IDs (match your host user)
PUID=1000
PGID=1000

# Data persistence location
STACK_BINDMOUNTROOT=/mnt/docker/stacks
STACK_NAME=stk-bain-00001

# Database credentials
POSTGRES_USER=bain
POSTGRES_PASSWORD=YourSecurePassword
POSTGRES_DB=bain
```

## Deployment Options

### Local Build (Development)

```bash
docker compose up -d
```

### Registry-Based (Production)

```bash
# Build and push images
export DOCKER_USER="your-username"
export DOCKER_PAT="your-personal-access-token"
./deploy.sh build
./deploy.sh push

# On target server
docker compose -f docker-compose.registry.yml up -d
```

## Architecture

| Service | Description | Port |
|---------|-------------|------|
| **Proxy** | Nginx reverse proxy | 8380 (external) |
| **App** | Django REST API | 8000 (internal) |
| **Web** | Imba frontend builder | 3000 (internal) |
| **DB** | PostgreSQL + pgvector | 5432 (internal) |

## Data Volumes

| Path | Purpose |
|------|---------|
| `${STACK_BINDMOUNTROOT}/DB` | PostgreSQL data |
| `${STACK_BINDMOUNTROOT}/App/Static` | Django static files |
| `${STACK_BINDMOUNTROOT}/App/Logs` | Seeding logs |
| `${STACK_BINDMOUNTROOT}/Web/Build` | Frontend build output |

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
- **CPU**: 0.5 cores max
- **Memory**: 2GB max
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

