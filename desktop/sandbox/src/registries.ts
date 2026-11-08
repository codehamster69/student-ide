/**
 * Hosts a "registries only" lab may reach, through the proxy sidecar.
 *
 * Package registries for the stacks the plan names (apt, pip, npm, Maven,
 * Gradle, crates, Go, conda) and GitHub release downloads. Everything else is
 * refused by the proxy, and every host it sees is logged as a net_conn event
 * (host name only, never contents). Shared with the server's teacher previews.
 */

export const REGISTRY_HOSTS: readonly string[] = [
  // apt (Ubuntu)
  "archive.ubuntu.com", "security.ubuntu.com", "ports.ubuntu.com", "ppa.launchpadcontent.net",
  // Python
  "pypi.org", "files.pythonhosted.org", "repo.anaconda.com", "conda.anaconda.org",
  // JavaScript
  "registry.npmjs.org", "registry.yarnpkg.com",
  // Java
  "repo.maven.apache.org", "repo1.maven.org", "plugins.gradle.org", "services.gradle.org", "downloads.gradle.org",
  // Rust and Go
  "crates.io", "index.crates.io", "static.crates.io", "static.rust-lang.org",
  "proxy.golang.org", "sum.golang.org", "storage.googleapis.com",
  // GitHub release assets
  "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com", "codeload.github.com",
];

/** tinyproxy filter lines: one anchored regex per host, sub-domains allowed. */
export function tinyproxyFilter(hosts: readonly string[] = REGISTRY_HOSTS): string {
  return hosts.map((h) => `^(.+\\.)?${h.replace(/\./g, "\\.")}$`).join("\n") + "\n";
}

export function hostAllowed(host: string, hosts: readonly string[] = REGISTRY_HOSTS): boolean {
  const h = host.toLowerCase().replace(/\.$/, "");
  return hosts.some((a) => h === a || h.endsWith(`.${a}`));
}
