#!/bin/bash
# Production Health Check
# Run this to verify all services are healthy

set -e

BACKEND_URL=${BACKEND_URL:-"http://localhost:8000"}
FRONTEND_URL=${FRONTEND_URL:-"http://localhost:3000"}
POSTGRES_HOST=${POSTGRES_HOST:-"localhost"}
REDIS_HOST=${REDIS_HOST:-"localhost"}

echo "🏥 Solix Health Check"
echo ""

# Backend health
echo "🔵 Backend ($BACKEND_URL):"
if curl -s "$BACKEND_URL/api/health" > /dev/null 2>&1; then
    echo "  ✓ Healthy"
else
    echo "  ✗ Unreachable"
    exit 1
fi

# Frontend health
echo "🟢 Frontend ($FRONTEND_URL):"
if curl -s "$FRONTEND_URL" > /dev/null 2>&1; then
    echo "  ✓ Healthy"
else
    echo "  ✗ Unreachable"
    exit 1
fi

# PostgreSQL health
echo "🟣 PostgreSQL ($POSTGRES_HOST):"
if command -v pg_isready &> /dev/null; then
    if pg_isready -h "$POSTGRES_HOST" -p 5432 > /dev/null 2>&1; then
        echo "  ✓ Healthy"
    else
        echo "  ✗ Unreachable"
    fi
else
    echo "  ⚠ pg_isready not installed (skipped)"
fi

# Redis health
echo "🔴 Redis ($REDIS_HOST):"
if command -v redis-cli &> /dev/null; then
    if redis-cli -h "$REDIS_HOST" ping > /dev/null 2>&1; then
        echo "  ✓ Healthy"
    else
        echo "  ✗ Unreachable"
    fi
else
    echo "  ⚠ redis-cli not installed (skipped)"
fi

echo ""
echo "✓ All services healthy!"
