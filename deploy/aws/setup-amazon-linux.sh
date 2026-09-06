#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# AWS Amazon Linux 2023 (AL2023) Provisioning Script
# ==============================================================================

echo "==> [1/5] Updating packages and installing Git & Docker..."
sudo dnf update -y
sudo dnf install -y git docker curl

echo "==> [2/5] Installing Docker Compose CLI plugin..."
sudo mkdir -p /usr/local/lib/docker/cli-plugins
DOCKER_ARCH="$(uname -m)"
sudo curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${DOCKER_ARCH}" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

echo "==> [3/5] Enabling and starting Docker daemon..."
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo "==> [4/5] Configuring 4GB Swap Space (prevents OOM during model inference)..."
if [ ! -f /swapfile ]; then
    sudo dd if=/dev/zero of=/swapfile bs=1M count=4096 status=progress
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "Swap allocated successfully."
else
    echo "Swap already exists. Skipping."
fi

echo "==> [5/5] Preparing Storage Directories..."
mkdir -p storage/vector_stores storage/uploads storage/data
chmod -R 775 storage

echo "------------------------------------------------------------------"
echo "Docker version: $(docker --version)"
echo "Docker compose: $(docker compose version)"
echo "Setup complete! Run 'newgrp docker' to apply group permissions."
echo "------------------------------------------------------------------"
