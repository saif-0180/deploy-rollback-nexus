#!/bin/bash

# Define the image name (you can change this to a custom name)
IMAGE_NAME="fix-deployment-orchestrator2"

# Step 1: Stop all running containers
echo "Stopping all running containers..."
docker ps -q | xargs -r docker stop

# Step 2: Remove all stopped containers
echo "Removing all stopped containers..."
docker ps -aq | xargs -r docker rm

# Step 3: Build Docker image from Dockerfile in the current directory
echo "Building Docker image..."
docker build -t "$IMAGE_NAME" .

# Step 4: Run the built Docker image
echo "Running the Docker image..."
# Dockerfile
#docker run -d  -p 5000:5000 --name "$IMAGE_NAME"-container "$IMAGE_NAME"

docker run -d -p 5000:5000 \
  -v /home/infadm/fixfiles:/app/fixfiles \
  -v /home/infadm/fixflow-deploy-orchestrator/inventory:/app/inventory \
  -v /home/infadm/.ssh:/app/.ssh \
  --name "$IMAGE_NAME"-container "$IMAGE_NAME"

# Optionally, show running containers
echo "Currently running containers:"
docker ps

