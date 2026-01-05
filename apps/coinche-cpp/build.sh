#!/bin/bash
set -e

echo "Building cointree_cpp..."

# Create build directory if it doesn't exist
mkdir -p build
cd build

# Run CMake
cmake ..

# Build
make -j$(nproc)

# Copy the generated shared library to the parent directory (python package root)
echo "Installing extension..."
cp cointree_cpp.cpython*.so ..

echo "Build and install complete."
