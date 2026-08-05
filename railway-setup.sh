#!/bin/bash
# One-command Railway deployment setup
# Usage: bash ./railway-setup.sh

set -e

echo "🚀 Solix Finance AI – Railway Deployment Setup"
echo ""

# Check prerequisites
if ! command -v railway &> /dev/null; then
    echo "📦 Installing Railway CLI..."
    npm install -g @railway/cli
fi

echo "✓ Railway CLI ready"
echo ""
echo "Next steps:"
echo ""
echo "1. Login to Railway:"
echo "   railway login"
echo ""
echo "2. Create project:"
echo "   railway init"
echo ""
echo "3. Add services:"
echo "   railway add postgres"
echo "   railway add redis"
echo ""
echo "4. Deploy backend:"
echo "   railway service backend"
echo "   railway up"
echo ""
echo "5. Deploy frontend:"
echo "   railway service frontend"
echo "   railway up"
echo ""
echo "6. View logs:"
echo "   railway logs"
echo ""
echo "7. Open dashboard:"
echo "   railway open"
echo ""
echo "See RAILWAY_DEPLOYMENT.md for detailed steps."
