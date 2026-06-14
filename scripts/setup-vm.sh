#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo." >&2
  exit 1
fi

# 1. Update package list and install prerequisites
apt-get update
apt-get install -y ca-certificates curl certbot git

# 2. Detect OS (Ubuntu/Debian) to download appropriate Docker repository
. /etc/os-release
OS_ID="${ID}"

if [[ "${OS_ID}" != "ubuntu" && "${OS_ID}" != "debian" ]]; then
  echo "Unsupported OS: ${OS_ID}. This script only supports Ubuntu and Debian." >&2
  exit 1
fi

# 3. Configure Docker GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL "https://download.docker.com/linux/${OS_ID}/gpg" -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# 4. Configure Docker APT repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${OS_ID} ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list

# 5. Install Docker engines
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 6. Enable and start Docker service
systemctl enable --now docker
echo "Docker environment successfully configured for ${OS_ID} (${VERSION_CODENAME})."
