#!/bin/bash
# Permanent SSH Tunnel Keep-Alive Script
# This script continuously monitors and restarts the tunnel if it dies

TUNNEL_CHECK_INTERVAL=30  # Check every 30 seconds
MAX_RETRIES=3
RETRY_DELAY=5

echo "Starting SSH tunnel monitor..."
echo "Checking tunnel health every ${TUNNEL_CHECK_INTERVAL} seconds"

while true; do
    # Check if tunnel is running
    if ! ps aux | grep -q "[s]sh.*6443"; then
        echo "[$(date)] Tunnel is down. Attempting restart..."
        
        # Try to restart tunnel with retries
        for attempt in $(seq 1 $MAX_RETRIES); do
            echo "[$(date)] Restart attempt $attempt of $MAX_RETRIES..."
            
            # Kill any existing tunnels
            pkill -f "ssh.*6443" 2>/dev/null
            pkill -f "gcloud.*ssh.*6443" 2>/dev/null
            sleep 2
            
            # Start tunnel via gcloud
            gcloud compute ssh swinvm15@k8s-master-001 \
              --zone=us-central1-a \
              -- -N -f \
              -o "ServerAliveInterval=30" \
              -o "ServerAliveCountMax=3" \
              -o "ExitOnForwardFailure=yes" \
              -L 6443:localhost:6443 \
              > /dev/null 2>&1
            
            sleep 5
            
            # Verify tunnel started
            if ps aux | grep -q "[s]sh.*6443"; then
                echo "[$(date)] ✓ Tunnel restarted successfully"
                
                # Test kubectl connectivity
                if kubectl get nodes > /dev/null 2>&1; then
                    echo "[$(date)] ✓ kubectl connectivity confirmed"
                    break
                else
                    echo "[$(date)] ⚠ Tunnel running but kubectl cannot connect"
                fi
            else
                echo "[$(date)] ✗ Failed to start tunnel (attempt $attempt)"
                if [ $attempt -lt $MAX_RETRIES ]; then
                    sleep $RETRY_DELAY
                fi
            fi
        done
        
        if ! ps aux | grep -q "[s]sh.*6443"; then
            echo "[$(date)] ✗ All restart attempts failed. Will retry in ${TUNNEL_CHECK_INTERVAL}s"
        fi
    else
        # Tunnel is running - verify it's working
        if ! kubectl get nodes > /dev/null 2>&1; then
            echo "[$(date)] ⚠ Tunnel exists but kubectl cannot connect. Forcing restart..."
            pkill -f "ssh.*6443"
        fi
    fi
    
    sleep $TUNNEL_CHECK_INTERVAL
done
