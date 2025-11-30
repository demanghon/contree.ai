#!/bin/bash

# Function to handle kill signal
cleanup() {
    echo "Stopping services..."
    kill $NX_PID
    exit
}

# Trap SIGINT (Ctrl+C)
trap cleanup SIGINT

# Start all services using Nx
echo "Starting services with Nx..."
npx nx run-many -t serve &
NX_PID=$!

echo "Services started."
echo "Frontend running at: http://localhost:4200"
echo "Backend running at: http://localhost:8000"

wait $NX_PID
