#!/bin/bash

# ISR Repository Production Deployment Script
# This script helps deploy the application in production

set -e

echo "🚀 ISR Repository Production Deployment"
echo "====================================="

# Check if .env.prod exists
if [ ! -f ".env.prod" ]; then
    echo "❌ .env.prod file not found!"
    echo "📝 Please create .env.prod file from env.prod.example:"
    echo "   cp env.prod.example .env.prod"
    echo "   # Then edit .env.prod with your actual values"
    exit 1
fi

# Load environment variables
export $(cat .env.prod | grep -v '^#' | xargs)

echo "📋 Environment Configuration:"
echo "   Database: ${POSTGRES_DB:-isrrepository}"
echo "   User: ${POSTGRES_USER:-isruser}"
echo "   Image Registry: ${IMAGE_REGISTRY:-ghcr.io}"
echo "   Image Namespace: ${IMAGE_NAMESPACE:-silvioheinze}"
echo "   Image Name: ${IMAGE_NAME:-isr-repository}"
echo "   Image Tag: ${IMAGE_TAG:-latest}"

# Check if we should try to pull from registry or build locally
echo ""
echo "🔍 Checking image availability..."

# Try to pull the main image
if docker pull "${IMAGE_REGISTRY:-ghcr.io}/${IMAGE_NAMESPACE:-silvioheinze}/${IMAGE_NAME:-isr-repository}:${IMAGE_TAG:-latest}" 2>/dev/null; then
    echo "✅ Main image found in registry"
    USE_REGISTRY=true
else
    echo "⚠️  Main image not found in registry, will build locally"
    USE_REGISTRY=false
fi

# Try to pull the nginx image
if docker pull "${IMAGE_REGISTRY:-ghcr.io}/${IMAGE_NAMESPACE:-silvioheinze}/${IMAGE_NAME:-isr-repository}-nginx:${IMAGE_TAG:-latest}" 2>/dev/null; then
    echo "✅ Nginx image found in registry"
else
    echo "⚠️  Nginx image not found in registry, will build locally"
    USE_REGISTRY=false
fi

# Set environment variables for docker compose
if [ "$USE_REGISTRY" = false ]; then
    echo ""
    echo "🔨 Building images locally..."
    export BUILD_LOCAL=true
else
    echo ""
    echo "📥 Using registry images..."
    export BUILD_LOCAL=false
fi

# Create external network if it doesn't exist
echo ""
echo "🌐 Setting up networks..."
if ! docker network ls | grep -q "proxy"; then
    echo "   Creating proxy network..."
    docker network create proxy
else
    echo "   Proxy network already exists"
fi

# Deploy with docker compose
echo ""
echo "🚀 Deploying application..."
if [ "$USE_REGISTRY" = true ]; then
    # Use registry images
    docker compose -f docker compose.prod.yml --env-file .env.prod up -d
else
    # Build locally
    docker compose -f docker compose.prod.yml --env-file .env.prod up -d --build
fi

echo ""
echo "✅ Deployment completed!"
echo ""
echo "📊 Service Status:"
docker compose -f docker compose.prod.yml ps

echo ""
echo "📝 Useful commands:"
echo "   View logs: docker compose -f docker compose.prod.yml logs -f"
echo "   Stop services: docker compose -f docker compose.prod.yml down"
echo "   Restart services: docker compose -f docker compose.prod.yml restart"
echo "   Update services: docker compose -f docker compose.prod.yml pull && docker compose -f docker compose.prod.yml up -d"
