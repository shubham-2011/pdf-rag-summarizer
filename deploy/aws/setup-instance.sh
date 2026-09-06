#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# AWS EC2 / Lightsail Provisioning Script for Document Intelligence Platform
# Tested on Ubuntu 22.04 & 24.04 LTS (x86_64 and aarch64 / Graviton)
# ==============================================================================

echo "==> [1/6] Updating system packages..."
sudo apt-get update -y && sudo apt-get upgrade -y
sudo apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    ufw \
    git \
    htop

echo "==> [2/6] Configuring 4GB Swap Space (prevents OOM during model inference)..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
    echo "Swap allocated successfully."
else
    echo "Swap already exists. Skipping."
fi

echo "==> [3/6] Installing Docker & Docker Compose Plugin..."
sudo install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
fi

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable and start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Add current user to docker group
sudo usermod -aG docker "$USER"

echo "==> [4/6] Configuring UFW Firewall..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'
sudo ufw --force enable

echo "==> [5/6] Preparing Storage Directories..."
mkdir -p storage/vector_stores storage/uploads storage/data
chmod -R 775 storage

echo "==> [6/6] Installation Complete!"
echo "------------------------------------------------------------------"
echo "Docker version: $(docker --version)"
echo "Docker compose version: $(docker compose version)"
echo ""
echo "NEXT STEPS:"
echo "1. Log out and log back in (or run 'newgrp docker') to apply docker group."
echo "2. Copy your .env.production file to .env"
echo "3. Run: docker compose -f deploy/aws/docker-compose.prod.yml up -d --build"
echo "4. Verify: curl http://localhost:80/api/health"
echo "------------------------------------------------------------------"
