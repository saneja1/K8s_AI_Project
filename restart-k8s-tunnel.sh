#!/bin/bash
# SSH Tunnel Restart Script for Kubernetes Master Access
# This script kills any existing SSH tunnels and creates a persistent one using gcloud

echo "Stopping existing SSH tunnels to port 6443..."
pkill -f "ssh.*6443"
pkill -f "gcloud.*ssh.*6443"
sleep 2

echo "Starting persistent SSH tunnel via gcloud..."
# Using gcloud compute ssh for automatic authentication
# Tunnel forwards localhost:6443 -> master-node:6443 (Kubernetes API)
gcloud compute ssh swinvm15@k8s-master-001 \
  --zone=us-central1-a \
  -- -N -f \
  -o "ServerAliveInterval=30" \
  -o "ServerAliveCountMax=3" \
  -L 6443:localhost:6443 \
  > /dev/null 2>&1

sleep 3

echo "Verifying tunnel is running..."
if ps aux | grep -q "[s]sh.*6443"; then
    echo "✓ SSH tunnel is active"
    echo "Tunnel details:"
    ps aux | grep "[s]sh.*6443" | grep -v grep
else
    echo "✗ Failed to start SSH tunnel"
    exit 1
fi

echo ""
echo "Testing kubectl connection..."
if kubectl get nodes > /dev/null 2>&1; then
    echo "✓ kubectl can reach the cluster"
else
    echo "⚠ kubectl cannot reach the cluster yet (may take a few seconds)"
fi

echo ""
echo "Tunnel setup complete. Access kubectl via localhost:6443"
