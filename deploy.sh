#!/bin/bash
# Deploy to Docker Hub or GitHub Container Registry
# Usage: bash ./deploy.sh [backend|frontend|all] [tag]
# Example: bash ./deploy.sh all v1.0.0

set -e

REGISTRY=${REGISTRY:-"ghcr.io"}
ORG=${ORG:-"$(git config user.name | tr ' ' '-' | tr '[:upper:]' '[:lower:]')"}
TAG=${2:-"latest"}
SERVICE=${1:-"all"}

if [ -z "$REGISTRY" ] || [ -z "$ORG" ]; then
    echo "Error: REGISTRY and ORG environment variables must be set"
    exit 1
fi

echo "📦 Deploying to $REGISTRY/$ORG"
echo "Tag: $TAG"

build_and_push() {
    local service=$1
    local image="$REGISTRY/$ORG/solix-$service"
    
    echo ""
    echo "🔨 Building $service..."
    docker build -t "$image:$TAG" -t "$image:latest" ./solix_minimal/$service
    
    echo "📤 Pushing $image:$TAG"
    docker push "$image:$TAG"
    docker push "$image:latest"
    
    echo "✓ Pushed to $image:$TAG"
}

case $SERVICE in
    backend)
        build_and_push "backend"
        ;;
    frontend)
        build_and_push "frontend"
        ;;
    all)
        build_and_push "backend"
        build_and_push "frontend"
        ;;
    *)
        echo "Usage: $0 [backend|frontend|all] [tag]"
        exit 1
        ;;
esac

echo ""
echo "✓ Deployment complete!"
echo ""
echo "Pull images:"
echo "  docker pull $REGISTRY/$ORG/solix-backend:$TAG"
echo "  docker pull $REGISTRY/$ORG/solix-frontend:$TAG"
