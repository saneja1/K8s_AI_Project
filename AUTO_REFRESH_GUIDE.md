# Auto-Refresh Feature Guide

## Overview
The Kubernetes Management Dashboard now includes automatic data refresh functionality to keep VM and Pod data up-to-date without manual intervention.

## Features

### 🔄 Automatic Data Refresh
- **Refresh Interval**: Every 30 seconds
- **What Gets Refreshed**: 
  - VM Status & Resources (CPU, Memory, Disk)
  - Pod Monitor (Pod statuses, resource usage)
  - Data Age columns update automatically
  - Live status indicators (green/yellow/red dots)

### ⏱️ Visual Countdown Timer
- Located in the top-right header
- Shows "Next refresh in: Xs" countdown
- Green color indicates active auto-refresh
- Updates in real-time

### 🎛️ Auto-Refresh Toggle
- Toggle switch in the top-right corner
- **ON (default)**: Data refreshes every 30 seconds automatically
- **OFF**: No automatic refresh, manual refresh only
- Persists across page interactions

## How It Works

### Automatic Refresh Logic
```
Every 30 seconds:
1. Fetch fresh VM data from GCP instances via SSH
2. Fetch fresh Pod data from Kubernetes cluster via kubectl
3. Update "Data Age" columns
4. Update live status indicators (green/yellow/red dots)
5. Refresh all metrics and statistics
```

### Manual Refresh Buttons
- **VM Status tab**: "🔄 Refresh" button
- **Pod Monitor tab**: "🔄 Refresh" button
- Clicking manual refresh resets the 30-second timer

### Data Freshness Indicators
- 🟢 **GREEN** (LIVE): Data is < 30 seconds old
- 🟡 **YELLOW** (STALE): Data is > 30 seconds old
- 🔴 **RED** (ERROR): Failed to fetch data

## Benefits

### 1. Real-Time Monitoring
- No need to manually click refresh
- Always see current VM and Pod states
- Catch issues immediately as they occur

### 2. Data Age Accuracy
- "Data Age" column shows exact staleness
- Format: "5s ago", "2m ago", "1h ago"
- Updates automatically every 30 seconds

### 3. Reduced Manual Effort
- Set it and forget it
- Dashboard maintains itself
- Focus on monitoring, not clicking

## Usage Tips

### Best Practices
1. **Keep auto-refresh ON** for active monitoring sessions
2. **Turn it OFF** if you need to analyze static data
3. **Use manual refresh** when you want immediate update

### Performance Considerations
- Auto-refresh performs SSH + kubectl calls every 30s
- Each refresh fetches data from 2 VMs (master + worker)
- Optimized: Only 2 SSH calls per VM (combined commands)
- Network-efficient: ~4 SSH + 1 kubectl call per refresh

### When to Disable Auto-Refresh
- Long meetings/presentations (to keep static view)
- Debugging specific issues (to freeze data)
- Reducing network traffic/costs
- Battery conservation on laptops

## Technical Details

### Timer Reset Behavior
The 30-second timer resets when:
1. Manual refresh button clicked
2. Auto-refresh toggle switched ON/OFF
3. Page reload or browser refresh
4. Tab switching (counts as page reload)

### Session State
Auto-refresh settings persist within the same browser session:
- Setting survives tab switches
- Setting survives manual refreshes
- Setting resets on browser close/reopen

## Troubleshooting

### "Next refresh in: 0s" stuck
- Indicates auto-refresh is trying to run
- Check SSH tunnel: `ps aux | grep "ssh.*6443"`
- Check kubectl: `kubectl get nodes`

### Data not updating
1. Verify auto-refresh toggle is **ON**
2. Check countdown timer is decreasing
3. Verify SSH tunnel is alive: `./restart-k8s-tunnel.sh`
4. Check dashboard logs for errors

### High CPU/network usage
- Expected: Auto-refresh uses resources every 30s
- Solution: Toggle OFF when not actively monitoring
- Alternative: Increase refresh interval (requires code change)

## Future Enhancements

Potential improvements (not yet implemented):
- [ ] Configurable refresh interval (15s, 30s, 60s, 120s)
- [ ] Per-tab auto-refresh (enable for VM only, disable for Pods)
- [ ] Pause on error (stop auto-refresh if data fetch fails)
- [ ] Background refresh (update without page flicker)
- [ ] Smart refresh (only update changed data)

## Related Documentation
- `restart-k8s-tunnel.sh`: SSH tunnel management script
- `SSH_SETUP_GUIDE.md`: SSH authentication setup
- `google-cloud-setup.md`: GCP VM configuration

## Support
For issues or questions about auto-refresh:
1. Check if SSH tunnel is alive
2. Verify kubectl connection to cluster
3. Review dashboard logs in the Host Validator tab
4. Test with manual refresh first
