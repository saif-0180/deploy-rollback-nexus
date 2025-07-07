
# Fix Deployment Orchestrator - Kubernetes Deployment

This document guides you through deploying the Fix Deployment Orchestrator application on Kubernetes.

## Prerequisites

1. Docker installed for building the container image
2. kubectl configured to access your Kubernetes cluster
3. Access to a container registry

## Build and Push Docker Image

```bash
# Build the Docker image
docker build -t fix-deployment-orchestrator:latest .

# Tag the image for your registry
docker tag fix-deployment-orchestrator:latest your-registry/fix-deployment-orchestrator:latest

# Push to registry
docker push your-registry/fix-deployment-orchestrator:latest
```

## SSH Keys Setup

Create a Kubernetes secret containing the SSH keys for connecting to the target VMs:

```bash
kubectl create secret generic ssh-keys \
  --from-file=id_rsa=/path/to/your/private/key \
  --from-file=id_rsa.pub=/path/to/your/public/key \
  --from-file=known_hosts=/path/to/your/known_hosts
```

## Create Inventory ConfigMap

Create a ConfigMap for the inventory:

```bash
kubectl create configmap inventory-config \
  --from-file=inventory.json=/path/to/your/inventory.json
```

Example inventory.json:
```json
{
  "vms": [
    {"name": "batch1", "type": "batch", "ip": "192.168.1.10"},
    {"name": "batch2", "type": "batch", "ip": "192.168.1.11"},
    {"name": "imdg1", "type": "imdg", "ip": "192.168.1.20"},
    {"name": "imdg2", "type": "imdg", "ip": "192.168.1.21"}
  ],
  "users": ["infadm", "abpwrk1"],
  "db_users": ["postgres", "dbadmin"],
  "systemd_services": ["hazelcast", "kafka", "zookeeper", "airflow-scheduler"]
}
```

## Deploy the Application

```bash
# Apply Kubernetes manifests
kubectl apply -f kubernetes/persistent-volume.yaml
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml

# Verify pods are running
kubectl get pods -l app=fix-deployment-orchestrator

# Get service URL
kubectl get service fix-deployment-orchestrator
```

## Accessing the Application

Once deployed, you can access the application at the external IP address provided by the LoadBalancer service.

## Best Practices for Production

1. **Security**:
   - Use Kubernetes Secrets for sensitive information
   - Implement RBAC for access control
   - Use network policies to restrict traffic

2. **High Availability**:
   - Configure multiple replicas for redundancy
   - Use Pod Disruption Budgets

3. **Monitoring**:
   - Set up Prometheus for metrics
   - Configure alerts for application health

4. **Storage**:
   - Ensure proper backup strategies for PersistentVolumes
   - Consider using a distributed storage solution
