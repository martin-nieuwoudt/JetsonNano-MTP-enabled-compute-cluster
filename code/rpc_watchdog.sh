#!/bin/bash
# rpc_watchdog.sh - self-healing monitor for the local ggml-rpc-server.
# Runs as a systemd service on EVERY node. Probes localhost:50052; if the
# port is not accepting connections (server crashed OR wedged with a full
# accept queue), it restarts llama-rpc.service. Fully local - no SSH, no
# session dependency. This is the "failover magic": a node can never stay
# down just because an SSH session ended.
PORT=50052
INTERVAL=30      # seconds between probes
COOLDOWN=60      # min seconds between restarts (avoids restart storms)
LAST=0
while true; do
  if timeout 3 bash -c "cat < /dev/null > /dev/tcp/127.0.0.1/$PORT" 2>/dev/null; then
    : # healthy - port accepting
  else
    NOW=$(date +%s)
    if [ $((NOW - LAST)) -ge $COOLDOWN ]; then
      echo "$(date) WATCHDOG: port $PORT not accepting - restarting llama-rpc.service"
      systemctl restart llama-rpc.service
      LAST=$NOW
      sleep $COOLDOWN
      continue
    fi
  fi
  sleep $INTERVAL
done
