# Proxy sidecar for "registries only" labs (desktop/sandbox/src/instance.ts).
# tinyproxy allows only the hosts in $SID_ALLOW (comma list, sub-domains included)
# and logs every CONNECT/GET host to stderr, which the runtime turns into net_conn events.
ARG BASE=ubuntu:24.04
FROM ${BASE}
RUN apt-get update && apt-get install -y --no-install-recommends tinyproxy \
    && rm -rf /var/lib/apt/lists/*
COPY entrypoint.sh /usr/local/bin/sidproxy
RUN chmod 755 /usr/local/bin/sidproxy
EXPOSE 8888
ENTRYPOINT ["/usr/local/bin/sidproxy"]
