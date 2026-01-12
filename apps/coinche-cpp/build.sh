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
echo "Installing extension to bin/..."
mkdir -p ../bin
cp cointree_cpp.cpython*.so ../bin/

echo "Build and install complete."
