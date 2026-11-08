# Dev/test image only: the same shape as the catalogue's rendered environments
# (backend/studentide/sandbox.py renders the real ones from a recipe):
# Ubuntu 24.04, user "student" (uid 1000, passwordless sudo), vim nano tmux git curl,
# plus gcc/make/python3 for the runtime's tests. Build: see docs/sandbox-runtime.md (Tests).
ARG BASE=ubuntu:24.04
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
      sudo vim nano tmux git curl ca-certificates gcc make libc6-dev python3 \
    && rm -rf /var/lib/apt/lists/* \
    && (userdel -r ubuntu 2>/dev/null || true) \
    && useradd -m -u 1000 -s /bin/bash student \
    && echo 'student ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/student && chmod 440 /etc/sudoers.d/student
USER student
WORKDIR /home/student
CMD ["sleep", "infinity"]
