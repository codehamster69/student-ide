# The pilot VM on Google Cloud

What runs today (set up 2026-10-26):

| | |
|---|---|
| project | `studentide-iiits-1026` (billing: Rohan's account) |
| VM | `studentide`, e2-medium, Ubuntu 24.04, 40 GB, zone `asia-south1-a` (Mumbai) |
| IP | static `studentide-ip`, 34.14.186.251; firewall rule `allow-web` (80, 443) |
| DNS | `studentide.hokora.xyz` A record in Vercel DNS |
| release | `gs://studentide-iiits-1026-deploy/studentide.tar.gz` + `deploy.env` (private bucket, Mumbai) |

The VM has no copy of the repo or of GitHub credentials. On every boot
`startup.sh` (instance metadata `startup-script`) installs Docker if needed,
pulls the release tarball and `.env` from the bucket, runs
`docker compose up -d --build`, then prints a smoke test to the serial console.

Deploy a new version from a checkout of the branch to ship:

```bash
P=studentide-iiits-1026; A="--zone asia-south1-a --project $P"
git archive --format=tar.gz -o /tmp/studentide.tar.gz HEAD
gcloud storage cp /tmp/studentide.tar.gz gs://$P-deploy/
gcloud compute instances stop studentide $A && gcloud compute instances start studentide $A
gcloud compute instances get-serial-port-output studentide $A | grep SMOKE
```

Use stop/start, not `reset`: a hard reset while Caddy is writing a
certificate leaves a truncated file (startup.sh detects and clears that case).
Change settings by editing `deploy.env` in the bucket the same way.
