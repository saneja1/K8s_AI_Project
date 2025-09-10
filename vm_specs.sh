#!/bin/bash

echo "=== COMPREHENSIVE VM SPECIFICATIONS ===="
echo ""

# Get VM instances with basic info
VMS=$(gcloud compute instances list --format="value(name,zone.basename(),status,machineType.basename(),disks[0].diskSizeGb,networkInterfaces[0].networkIP,networkInterfaces[0].accessConfigs[0].natIP)")

echo "VM_NAME          ZONE         STATUS    MACHINE_TYPE  CPU_CORES  MEMORY_GB  DISK_GB  INTERNAL_IP      EXTERNAL_IP"
echo "=====================================================================================================  "

while IFS=$'\t' read -r name zone status machine_type disk_gb internal_ip external_ip; do
    # Get CPU and memory for the machine type
    if [[ "$machine_type" == "e2-medium" ]]; then
        cpu_cores="2"
        memory_gb="4"
    elif [[ "$machine_type" == "e2-small" ]]; then
        cpu_cores="2" 
        memory_gb="2"
    elif [[ "$machine_type" == "e2-standard-2" ]]; then
        cpu_cores="2"
        memory_gb="8"
    elif [[ "$machine_type" == "e2-standard-4" ]]; then
        cpu_cores="4"
        memory_gb="16"
    else
        # Get from gcloud for other types
        specs=$(gcloud compute machine-types describe "$machine_type" --zone="$zone" --format="value(guestCpus,memoryMb)" 2>/dev/null)
        if [[ -n "$specs" ]]; then
            cpu_cores=$(echo "$specs" | cut -f1)
            memory_mb=$(echo "$specs" | cut -f2)
            memory_gb=$((memory_mb / 1024))
        else
            cpu_cores="N/A"
            memory_gb="N/A"
        fi
    fi
    
    printf "%-16s %-12s %-9s %-13s %-10s %-10s %-8s %-16s %s\n" \
        "$name" "$zone" "$status" "$machine_type" "$cpu_cores" "$memory_gb" "$disk_gb" "$internal_ip" "$external_ip"
done <<< "$VMS"

echo ""
echo "Available Resources per Machine Type:"
echo "- e2-medium: 2 vCPUs, 4 GB RAM"
echo "- e2-small: 2 vCPUs, 2 GB RAM" 
echo "- e2-standard-2: 2 vCPUs, 8 GB RAM"
echo "- e2-standard-4: 4 vCPUs, 16 GB RAM"
