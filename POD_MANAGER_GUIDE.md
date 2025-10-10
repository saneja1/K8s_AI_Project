# 🎯 Pod Manager Tab - User Guide

## Overview
The new **Pod Manager** tab allows you to create and manage Kubernetes pods through an easy-to-use web interface - no command line needed!

## ✨ Features

### 1. **Create New Pods** 🚀
- **Pod Templates**: Choose from pre-configured templates
  - `stress-tester-2` - Your stress testing app
  - `nginx` - Web server
  - `redis` - In-memory database
  - `custom` - Bring your own image

- **Configuration Options**:
  - Pod Name
  - Number of Replicas (1-10)
  - CPU Limit (0.25 to 2 cores)
  - Memory Limit (256Mi to 4Gi)
  - Target Node (auto/master/worker)
  - Container Port
  - Custom Docker Image

### 2. **View Existing Pods** 📦
- Real-time list of all pods across all namespaces
- Shows pod status, node placement, IP addresses
- Refresh button to update the list

### 3. **Delete Pods** 🗑️
- Easy pod deletion by name
- Confirmation messages
- Auto-refresh after deletion

## 🎯 How to Use

### Creating Your First Pod:

1. **Open Dashboard**: http://localhost:8501
2. **Go to "Pod Manager" tab**
3. **Fill out the form**:
   - Template: Select `stress-tester-2`
   - Name: Leave as `stress-tester-2` or customize
   - Replicas: `1`
   - CPU Limit: `1000m (1 core)`
   - Memory Limit: `2Gi`
   - Target Node: `auto (scheduler decides)`

4. **Click "🚀 Create Pod"**
5. **Wait for success message**
6. **Check pod status** in the "Existing Pods" section

### Example: Creating stress-tester-2

**Basic Setup:**
```
Template: stress-tester-2
Name: stress-tester-2
Replicas: 1
CPU: 1000m (1 core)
Memory: 2Gi
Node: auto
```

**Advanced (Force to Worker):**
```
Template: stress-tester-2
Name: stress-tester-2
Replicas: 1
CPU: 1000m (1 core)
Memory: 2Gi
Node: k8s-worker-01 (worker) ← Forces to worker!
```

### Testing the New Pod:

After creation, get the pod IP:
```bash
kubectl get pods -o wide
```

Then test it (from VM):
```bash
curl "http://POD_IP:5000/status"
curl "http://POD_IP:5000/stress-cpu?seconds=60"
```

## 🎓 Use Cases

### 1. **A/B Testing**
- Run stress-tester (original) + stress-tester-2 simultaneously
- Compare performance with different resource limits
- Test load distribution

### 2. **Multi-Node Testing**
- Create stress-tester-2 on master
- Original stress-tester stays on worker
- Stress both → Watch both nodes spike in dashboard

### 3. **Scaling Experiments**
- Create stress-tester-2 with 3 replicas
- See how Kubernetes distributes them
- Test resource contention

### 4. **Resource Limit Testing**
- Create stress-tester-2 with 4Gi memory limit
- Stress it to 3.5 GB → Survives
- Compare to original with 2Gi limit

## 🛠️ Behind the Scenes

The Pod Manager creates a Kubernetes Deployment YAML and applies it using kubectl:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: stress-tester-2
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: stress-tester-2
        image: us-central1-docker.pkg.dev/.../stress-tester:latest
        resources:
          limits:
            cpu: "1000m"
            memory: "2Gi"
      nodeSelector:  # Optional
        kubernetes.io/hostname: k8s-worker-01
```

## 📊 Monitoring

After creating pods, monitor them in:
- **Pod Manager tab** → Existing Pods section
- **Pod Monitor tab** → See all pods with live status
- **VM Status tab** → See resource usage on nodes

## ⚠️ Important Notes

1. **Pod Names Must Be Unique**: Can't have two deployments with same name
2. **Image Must Be Accessible**: For stress-tester-2, the image is already in Artifact Registry
3. **Node Selector**: If target node doesn't exist or has issues, pod stays Pending
4. **Resource Limits**: Don't exceed node capacity (total 2 cores, 3.8 GB per node)
5. **Deletion**: Deletes the deployment (all replicas)

## 🎯 Next Steps

1. Try creating `stress-tester-2` with different specs
2. Run stress tests on both pods simultaneously
3. Watch resource distribution in VM Status tab
4. Experiment with different pod templates (nginx, redis)

Enjoy your new Pod Manager! 🚀
