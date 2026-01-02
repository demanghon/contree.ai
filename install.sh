#!/bin/bash
set -e

echo "==========================================="
echo "  Kermit-Coinche Environment Installer"
echo "  Target: Ubuntu Server"
echo "==========================================="

# 1. System Dependencies
echo "[1/6] Installing System Dependencies..."
sudo apt-get update
sudo apt-get install -y \
    curl \
    git \
    build-essential \
    libssl-dev \
    pkg-config \
    software-properties-common

# 2. Python 3.11
echo "[2/6] Installing Python 3.11..."
# Check if python3.11 is available, if not add PPA
if ! command -v python3.11 &> /dev/null; then
    echo "Python 3.11 not found. Adding deadsnakes PPA..."
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt-get update
fi
sudo apt-get install -y python3.11 python3.11-dev python3.11-venv

# 3. Rust
echo "[3/6] Installing Rust..."
if ! command -v rustc &> /dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
else
    echo "Rust is already installed."
fi

# 4. Node.js (for Nx)
echo "[4/6] Installing Node.js & Nx..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
# Install Nx globally
sudo npm install -g nx

# 5. Poetry
echo "[5/6] Installing Poetry..."
if ! command -v poetry &> /dev/null; then
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

# 6. Global Python Tools
echo "[6/6] Installing Maturin..."
# Install maturin via pip (or pipx if preferred, but pip is simple for server envs)
# Ensure we use the correct pip or install it for the user
python3.11 -m ensurepip --upgrade
python3.11 -m pip install --user maturin

echo "==========================================="
echo "✅ Installation Complete!"
echo "==========================================="
echo "Please run the following command to load environment variables:"
echo "    source \$HOME/.cargo/env"
echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "Then install project dependencies:"
echo "    npm install"
echo "    cd apps/coinche-ml && poetry install"
