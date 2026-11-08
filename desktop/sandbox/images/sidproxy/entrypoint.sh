#!/bin/sh
# Writes the tinyproxy config from $SID_ALLOW and runs it in the foreground.
set -e
mkdir -p /run/sidproxy
: > /run/sidproxy/filter
IFS=,
for h in ${SID_ALLOW:-}; do
  [ -n "$h" ] && printf '^(.+\\.)?%s$\n' "$(printf '%s' "$h" | sed 's/\./\\./g')" >> /run/sidproxy/filter
done
unset IFS
cat > /run/sidproxy/tinyproxy.conf <<CONF
User nobody
Group nogroup
Port 8888
Listen 0.0.0.0
Timeout 600
MaxClients 64
LogLevel Connect
Filter "/run/sidproxy/filter"
FilterType ere
FilterDefaultDeny Yes
FilterURLs Off
ConnectPort 443
ConnectPort 80
DisableViaHeader Yes
CONF
exec tinyproxy -d -c /run/sidproxy/tinyproxy.conf
