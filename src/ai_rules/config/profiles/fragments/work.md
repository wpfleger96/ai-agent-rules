## AWS CLI

**Rule:** `--profile <account>-<env>--<role> --region us-west-2`
**Format:** `--profile data-lake-staging--admin` (✅) not `--profile staging-admin` (❌)
**Regex:** `^[a-z-]+-(dev|staging|production)--[a-z-]+$`

---

## Work Laptop: uv Package Resolution in Personal Repos

When working in `~/Development/Personal/*` repos, `uv sync` or `uv lock` may fail with
metadata errors (e.g., "Metadata field Name not found") because the corporate WARP VPN
intercepts traffic to `pypi.org` and routes it through Artifactory, which can't process
modern Python wheel metadata (Metadata-Version 2.4+).

**The fix is a simple VPN toggle — nothing else.** The package metadata is NOT broken.
The local uv cache is NOT corrupted. Do NOT attempt to clear caches, reinstall packages,
debug metadata, or investigate package build configurations. Just disconnect the VPN,
run the uv command, and reconnect:

```bash
warp-cli disconnect
uv sync  # or uv lock, uv pip install, etc.
warp-cli connect
```

Always reconnect immediately after — WARP is the corporate VPN and must stay active for
work network resources. This only affects personal repos; work repos use Artifactory
intentionally.

## Work Laptop: npm Registry Access in Personal Repos

The same WARP interception applies to npm: direct access to `registry.npmjs.org` is
hard-blocked by Cloudflare Gateway (Dependency Confusion policy — see
go/dependencyconfusionnpm), and the machine-level `~/.npmrc` routes npm traffic through
Artifactory instead. Personal repos must never resolve or lock against Artifactory.

Same fix as uv — toggle the VPN around network-touching npm/pnpm commands (install,
import, add, update) and reconnect immediately after:

```bash
warp-cli disconnect
pnpm install  # or npm install, pnpm import, pnpm add, etc.
warp-cli connect
```

Additionally, personal JS repos should commit a project-level `.npmrc` containing
`registry=https://registry.npmjs.org/` so the machine-level Artifactory registry can
never leak in (a no-op in CI, where npmjs is the default). pnpm lockfiles are
registry-agnostic, but npm's `package-lock.json` embeds resolved URLs — never commit
one generated against Artifactory.
