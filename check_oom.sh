container_name="$1"
# show OOMKilled flag, last exit code, and error
docker inspect -f '{{.State.OOMKilled}} {{.State.ExitCode}} {{.State.Error}}' $container_name
# also watch restarts:
docker inspect -f '{{.RestartCount}} {{.State.StartedAt}} {{.State.FinishedAt}}' $container_name

sudo grep -E "Out of memory|Killed process|oom-killer" /var/log/syslog /var/log/kern.log 2>/dev/null

CID=$(docker inspect -f '{{.Id}}' $container_name)
PID=$(docker inspect -f '{{.State.Pid}}' $container_name)
echo "CID=$CID  PID=$PID"

# sometimes the kernel log mentions the cgroup path with the short ID:
sudo journalctl -k --since "2 hours ago" | grep -E "${CID:0:12}|docker/${CID}|docker-${CID}"

CGPATH="/sys/fs/cgroup/system.slice/docker-${CID}.scope"
[ -d "$CGPATH" ] || CGPATH="/sys/fs/cgroup/docker/$CID"
sudo cat "$CGPATH/memory.events" 2>/dev/null

CGPATH="/sys/fs/cgroup/memory/docker/$CID"
sudo cat "$CGPATH/memory.oom_control" 2>/dev/null
sudo cat "$CGPATH/memory.failcnt" 2>/dev/null

sudo journalctl -u docker --since "2 hours ago"
