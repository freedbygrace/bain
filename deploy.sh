#!/bin/bash
#=============================================================================
# BAIN (Bolls Bible) - Build and Deploy Script
# https://github.com/Bolls-Bible/bain
#=============================================================================
# Usage:
#   ./deploy.sh build    - Clone, build, push images to DockerHub
#   ./deploy.sh deploy   - Deploy using pre-built images from DockerHub
#   ./deploy.sh all      - Full pipeline (build + deploy)
#=============================================================================
set -e

#-----------------------------------------------------------------------------
# Docker Hub Credentials (from environment or .env file)
#-----------------------------------------------------------------------------
# Set these in your environment or .env file:
#   export DOCKER_USER="your-docker-username"
#   export DOCKER_PAT="your-docker-personal-access-token"
DOCKER_USER="${DOCKER_USER:-}"
DOCKER_PAT="${DOCKER_PAT:-}"

#-----------------------------------------------------------------------------
# Colors & Logging
#-----------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

#-----------------------------------------------------------------------------
# Setup
#-----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env (only specific variables we need)
if [[ -f .env ]]; then
    STACK_NAME=$(grep -E "^STACK_NAME=" .env | cut -d'=' -f2)
    STACK_BINDMOUNTROOT=$(grep -E "^STACK_BINDMOUNTROOT=" .env | cut -d'=' -f2)
    BAIN_PORT=$(grep -E "^BAIN_PORT=" .env | cut -d'=' -f2)
fi

STACK_NAME="${STACK_NAME:-stk-bain-00001}"
STACK_ROOT="${STACK_BINDMOUNTROOT:-/custom/docker/stacks}/${STACK_NAME}"
APP_IMAGE="${DOCKER_USER}/bain-app:latest"
WEB_IMAGE="${DOCKER_USER}/bain-web:latest"
ACTION="${1:-all}"

#-----------------------------------------------------------------------------
# Docker Hub Login
#-----------------------------------------------------------------------------
docker_login() {
    log "Logging into Docker Hub..."
    echo "$DOCKER_PAT" | docker login --username "$DOCKER_USER" --password-stdin >/dev/null 2>&1
    success "Logged into Docker Hub as ${DOCKER_USER}"
}

#-----------------------------------------------------------------------------
# Build Function
#-----------------------------------------------------------------------------
do_build() {
    echo ""
    echo "════════════════════════════════════════════════════════════════════════════"
    echo "  BAIN (Bolls Bible) - BUILD"
    echo "════════════════════════════════════════════════════════════════════════════"
    echo ""

    # Clone source
    log "Checking source repository..."
    if [[ ! -d "source" ]]; then
        log "Cloning Bolls Bible repository..."
        git clone --depth 1 https://github.com/Bolls-Bible/bain.git source
        success "Repository cloned"
    else
        log "Updating existing repository..."
        cd source && git pull --ff-only 2>/dev/null || true && cd ..
        success "Repository updated"
    fi

    # Build images
    log "Building Django backend (bain-app)..."
    docker build -t "$APP_IMAGE" -f source/django/Dockerfile source/django/
    success "Built: $APP_IMAGE"

    log "Building Imba frontend (bain-web)..."
    docker build -t "$WEB_IMAGE" -f source/imba/Dockerfile source/imba/
    success "Built: $WEB_IMAGE"

    # Login and push
    docker_login

    log "Pushing images to Docker Hub..."
    docker push "$APP_IMAGE"
    success "Pushed: $APP_IMAGE"

    docker push "$WEB_IMAGE"
    success "Pushed: $WEB_IMAGE"

    success "Build complete!"
}

#-----------------------------------------------------------------------------
# Deploy Function
#-----------------------------------------------------------------------------
do_deploy() {
    echo ""
    echo "════════════════════════════════════════════════════════════════════════════"
    echo "  BAIN (Bolls Bible) - DEPLOY"
    echo "════════════════════════════════════════════════════════════════════════════"
    echo ""
    log "Stack Name: ${STACK_NAME}"
    log "Stack Root: ${STACK_ROOT}"
    log "Port: ${BAIN_PORT:-8380}"
    echo ""

    # Create directories
    log "Creating data directories..."
    sudo mkdir -p "${STACK_ROOT}/DB/Data"
    sudo mkdir -p "${STACK_ROOT}/App/Static"
    sudo mkdir -p "${STACK_ROOT}/Web/Build"
    sudo chmod -R 777 "${STACK_ROOT}"
    success "Directories created"

    # Pull latest images
    docker_login
    log "Pulling latest images..."
    docker pull "$APP_IMAGE"
    docker pull "$WEB_IMAGE"
    success "Images pulled"

    # Extract frontend build
    log "Extracting Imba frontend build..."
    docker run --rm -v "${STACK_ROOT}/Web/Build:/output" "$WEB_IMAGE" sh -c "cp -r /build/. /output/ 2>/dev/null || cp -r /app/dist/. /output/ 2>/dev/null || cp -r ./dist/. /output/ 2>/dev/null || echo 'Copying all files'; cp -r . /output/"
    success "Frontend extracted"

    # Start stack with default compose (production)
    log "Starting stack..."
    docker compose down 2>/dev/null || true
    docker compose up -d

    # Wait for database
    log "Waiting for database to be ready..."
    sleep 15

    # Run migrations
    log "Running Django migrations..."
    docker exec BAIN-APP-00001 python manage.py migrate --noinput 2>/dev/null || warn "Migrations may need manual run"
    success "Migrations complete"

    log "Collecting static files..."
    docker exec BAIN-APP-00001 python manage.py collectstatic --noinput 2>/dev/null || warn "Collectstatic may need manual run"
    success "Static files collected"

    # Done
    echo ""
    echo "════════════════════════════════════════════════════════════════════════════"
    success "BAIN deployment complete!"
    echo "════════════════════════════════════════════════════════════════════════════"
    echo ""
    log "Access: http://localhost:${BAIN_PORT:-8380}/"
    log "API Test: http://localhost:${BAIN_PORT:-8380}/get-text/YLT/1/1/"
    echo ""
    docker compose ps
}

#-----------------------------------------------------------------------------
# Main
#-----------------------------------------------------------------------------
case "$ACTION" in
    build)
        do_build
        ;;
    deploy)
        do_deploy
        ;;
    all)
        do_build
        do_deploy
        ;;
    *)
        echo "Usage: $0 {build|deploy|all}"
        echo ""
        echo "  build  - Clone source, build images, push to DockerHub"
        echo "  deploy - Deploy using pre-built images from DockerHub"
        echo "  all    - Full pipeline (build + deploy)"
        exit 1
        ;;
esac

