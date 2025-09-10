# Kubeadm Cluster Setup Guide
# 2 GCP VMs: k8s-node-1 (master) + k8s-node-2 (worker)

## Prerequisites Check
1. Both VMs running Ubuntu 22.04
2. Both VMs have 2+ CPUs, 4GB+ RAM  
3. Network connectivity between VMs
4. SSH access to both VMs

## Phase 1: Prepare Both VMs (Run on BOTH k8s-node-1 and k8s-node-2)

### 1.1 System Updates
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.2 Install Container Runtime (Docker)
```bash
# Install Docker
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# Configure Docker daemon
sudo tee /etc/docker/daemon.json <<EOF
{
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m"
  },
  "storage-driver": "overlay2"
}
EOF

sudo systemctl restart docker
```

### 1.3 Disable Swap
```bash
sudo swapoff -a
sudo sed -i '/swap/d' /etc/fstab
```

### 1.4 Configure Kernel Modules
```bash
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

sudo modprobe overlay
sudo modprobe br_netfilter
```

### 1.5 Configure Sysctl
```bash
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF

sudo sysctl --system
```

### 1.6 Install kubeadm, kubelet, kubectl
```bash
# Add Kubernetes apt repository
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl

curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.28/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.28/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list

# Install Kubernetes components
sudo apt update
sudo apt install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl

# Enable kubelet
sudo systemctl enable kubelet
```

## Phase 2: Initialize Master Node (ONLY on k8s-node-1)

### 2.1 Initialize Cluster
```bash
# Initialize the cluster with pod network CIDR
sudo kubeadm init --pod-network-cidr=10.244.0.0/16 --apiserver-advertise-address=<MASTER_INTERNAL_IP>

# Configure kubectl for regular user
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

### 2.2 Install CNI Plugin (Flannel)
```bash
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml
```

### 2.3 Get Join Token
```bash
# This command will output the join command for worker nodes
kubeadm token create --print-join-command
```

## Phase 3: Join Worker Node (ONLY on k8s-node-2)

### 3.1 Join the Cluster
```bash
# Run the join command from step 2.3 (example):
sudo kubeadm join <MASTER_IP>:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>
```

## Phase 4: Verification (On Master Node)

### 4.1 Check Nodes
```bash
kubectl get nodes -o wide
```

### 4.2 Check System Pods
```bash
kubectl get pods -A
```

### 4.3 Test Deployment
```bash
kubectl create deployment nginx --image=nginx
kubectl expose deployment nginx --port=80 --type=NodePort
kubectl get svc nginx
```

## Firewall Rules (GCP)
```bash
# Allow Kubernetes API server
gcloud compute firewall-rules create k8s-api-server --allow tcp:6443 --source-ranges 10.0.0.0/8

# Allow kubelet API
gcloud compute firewall-rules create k8s-kubelet --allow tcp:10250 --source-ranges 10.0.0.0/8

# Allow node port services
gcloud compute firewall-rules create k8s-nodeports --allow tcp:30000-32767 --source-ranges 0.0.0.0/0

# Allow flannel
gcloud compute firewall-rules create k8s-flannel --allow udp:8472 --source-ranges 10.0.0.0/8
```

## Troubleshooting Commands
```bash
# Check kubelet logs
sudo journalctl -u kubelet -f

# Check container runtime
sudo docker ps

# Reset cluster (if needed)
sudo kubeadm reset
sudo rm -rf /etc/kubernetes/
sudo rm -rf ~/.kube/
```
