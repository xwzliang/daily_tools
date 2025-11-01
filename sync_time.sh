# See current status
timedatectl

# If systemd-timesyncd is used, restart and force sync:
# sudo systemctl restart systemd-timesyncd
# sudo timedatectl set-ntp true

# Or install/use chrony (recommended for VMs)
sudo apt-get update && sudo apt-get install -y chrony
sudo systemctl enable --now chrony

# Check sources and offsets
chronyc tracking
chronyc sources -v

# 2.1 Backup and replace config with a minimal, solid one
# 1) Backup and write a clean config
sudo cp /etc/chrony/chrony.conf /etc/chrony/chrony.conf.bak.$(date +%s)

sudo tee /etc/chrony/chrony.conf >/dev/null <<'EOF'
# Minimal client config
pool time.cloudflare.com iburst
pool time.google.com iburst
pool pool.ntp.org iburst

# Step the clock immediately on large offsets (first 3 updates)
makestep 1.0 3

# Keep RTC in sync (harmless in VMs too)
rtcsync

# Standard files
driftfile /var/lib/chrony/chrony.drift
logdir /var/log/chrony
EOF

# 2) Restart chrony
sudo systemctl enable --now chrony
sudo systemctl restart chrony

# This queries 1 server and *steps* the clock, then exits.
# If DNS is slow in your network, repeat once with the other server.
sudo chronyd -q 'server time.cloudflare.com iburst' || true
sudo chronyd -q 'server time.google.com iburst'    || true