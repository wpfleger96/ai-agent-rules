## Work Laptop: Personal Repo Location

On the work laptop, personal repos live under `~/Development/Personal/<repo>` — not `~/Development/<repo>` as on personal machines. This overrides the path-resolution rule and the Personal Infrastructure table paths.

## AWS CLI

**Rule:** `--profile <account>-<env>--<role> --region us-west-2`
**Format:** use `--profile data-lake-staging--admin`, not `--profile staging-admin`.
**Regex:** `^[a-z-]+-(dev|staging|production)--[a-z-]+$`

## Work Laptop: Package Registries in Personal Repos

The corporate WARP VPN routes PyPI and npm traffic through Artifactory, which breaks personal repos (`~/Development/Personal/*`): `uv sync`/`uv lock` fail with metadata errors (e.g., "Metadata field Name not found") because Artifactory can't process Metadata-Version 2.4+ wheels, and direct access to `registry.npmjs.org` is blocked by Cloudflare Gateway's Dependency Confusion policy (go/dependencyconfusionnpm), so the machine-level `~/.npmrc` points npm at Artifactory.

The cause is the VPN, so the whole fix is a VPN toggle around network-touching `uv`/`npm`/`pnpm` commands (sync, lock, install, add, import, update). Don't clear caches, reinstall, or debug metadata. Reconnect immediately after, since WARP must stay up for work resources:

```bash
warp-cli disconnect
uv sync  # or uv lock, pnpm install, npm install, pnpm add, etc.
warp-cli connect
```

Work repos use Artifactory intentionally. Personal JS repos commit a project `.npmrc` with `registry=https://registry.npmjs.org/` so Artifactory can't leak in (a no-op in CI). pnpm lockfiles are registry-agnostic, but `package-lock.json` embeds resolved URLs: never commit one generated against Artifactory.
