#!/bin/bash
set -e

# ── Pre-flight checks ──────────────────────────────────────
echo "🔍 Checking prerequisites..."

if ! command -v docker &>/dev/null; then
    echo "❌ Docker not found. Install Docker Desktop or docker-ce for WSL."
    exit 1
fi

if ! docker info 2>/dev/null | grep -q "Runtimes.*nvidia"; then
    echo "⚠️  NVIDIA container runtime not detected."
    echo "   Install: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html"
    echo "   Continuing anyway (will fail at runtime if GPU is needed)..."
fi

# Verify GPU is visible inside Docker
if docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi &>/dev/null; then
    echo "✅ GPU accessible from Docker"
else
    echo "⚠️  nvidia-smi failed inside container. Check:"
    echo "   1. NVIDIA drivers installed in Windows"
    echo "   2. nvidia-container-toolkit installed in WSL"
    echo "   3. Docker Desktop → Settings → Resources → WSL Integration enabled"
fi

# ── Build and deploy ────────────────────────────────────────
echo ""
echo "🔨 Building and starting containers..."
docker compose -f docker-compose.prod.yml up --build -d

echo ""
echo "✅ Deployment complete!"
echo "   App:  http://localhost:8000"
echo "   Logs: docker compose -f docker-compose.prod.yml logs -f"
