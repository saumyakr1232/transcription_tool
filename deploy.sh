#!/bin/bash

# Build and start the containers
echo "Building and starting Docker containers..."
docker compose -f docker-compose.prod.yml up --build -d

echo "Deployment complete! Application is running on http://localhost:8000"
