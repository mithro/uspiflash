# Releasing

This project is a **rolling release**. There are no manual version bumps: the
version is derived from `git describe` by `hatch-vcs` — `X.Y` at a `vX.Y`
tag, `X.Y.postN` N commits after it — and **every green push to `main`
publishes a new package** automatically:

- [`.github/workflows/deb.yml`](https://github.com/mithro/uspiflash/blob/main/.github/workflows/deb.yml) ("Debian packages") — on every push and PR, its
  `test` job runs the gates (ruff, mypy --strict, pytest with coverage); a
  green run is what "mergeable" means. Then it builds `python3-uspiflash` for
  Debian bookworm, trixie, forky and sid with
  [`mithro/apt-repo-action`](https://github.com/mithro/apt-repo-action)'s shared
  `build-deb`, install-tests each, and, on `main` only, republishes the signed
  apt repository on GitHub Pages (<https://mith.ro/uspiflash/>). The .deb's
  version is the wheel's plus the suite: `X.Y.postN~deb12` (bookworm),
  `~deb13` (trixie), `~deb14` (forky), nothing for sid; a pull request's
  preview build adds `~pr<P>`.
- [`.github/workflows/publish-pypi.yml`](https://github.com/mithro/uspiflash/blob/main/.github/workflows/publish-pypi.yml) — builds and uploads the wheel + sdist
  to PyPI when "Debian packages" **succeeds** on `main` (`workflow_run`; a
  failed or cancelled run publishes nothing, and the checkout is pinned to the
  SHA it validated).

Merges to `main` use merge commits (the only merge the repository allows), so
a pull request's preview version always sorts below the build of its merge.

`python3-uspiflash` depends on `python3-spiflash`, which is not in Debian:
[`.github/apt-packaging.toml`](https://github.com/mithro/uspiflash/blob/main/.github/apt-packaging.toml)'s
`[[depends]]` entry names `mithro/spiflash`'s apt repository, and `build-deb`
adds it to the build and install-test containers automatically.

## Tags

Tags are the only human input to the version. `v0.0` sits on the root commit
(so `git describe` works from the start of history). To cut a new series, push
an annotated `vX.Y` tag on `main` (a GitHub tag ruleset only admits
`vXX.ZZZ`-shaped tags) — the next green run publishes `X.Y`, and every commit
after it `X.Y.postN`. Never move or delete a tag that has been published from.

## One-time setup

**No secret or key is ever committed to the repo.**

### 1. PyPI trusted publishing (OIDC)

Registered 2026-09-28 — no action left:

- PyPI project name: `uspiflash`
- Owner: `mithro`
- Repository name: `uspiflash`
- Workflow name: [`publish-pypi.yml`](https://github.com/mithro/uspiflash/blob/main/.github/workflows/publish-pypi.yml)
- Environment name: `pypi`

The GitHub repo's **Environment** named `pypi` exists. No secrets needed —
OIDC handles auth.

Until the pending publisher's first successful upload, the publish workflow
runs but its upload step fails safely; `skip-existing: true` makes re-runs
idempotent.

### 2. apt repo signing key

The private half of the repository's own key is the `APT_GPG_PRIVATE_KEY`
repository secret (set on `mithro/uspiflash` on 2026-09-29); the publish
workflow exports the public half as `uspiflash.gpg` (binary) and
`uspiflash.asc` (armoured) at the site root. The key was made as
apt-repo-action's conventions.md says, and kept only in the maintainer's
keyring:

```sh
gpg --batch --passphrase '' --quick-gen-key \
  'uspiflash apt repository <me@mith.ro>' rsa4096 sign never
gpg --armor --export-secret-keys 'uspiflash apt repository' \
  | gh secret set APT_GPG_PRIVATE_KEY --repo mithro/uspiflash
```

Fingerprint: `2E19 5D58 706D 44E8 5704  1566 04FA D17C 2A3B 8344`.

### 3. GitHub Pages

Settings → Pages → Source: **GitHub Actions** (`gh api repos/mithro/uspiflash/pages
-X POST -f build_type=workflow`), with HTTPS enforced, and the `github-pages`
environment limited to deployments from `main`.

At creation, the Pages API reported `html_url: http://mith.ro/uspiflash/`
(`build_type: workflow`, as expected) — plain `http`, not `https`. This
matches `mithro.github.io` carrying the `mith.ro` domain: HTTPS certificate
issuance for a newly-attached custom domain lags behind the domain's own
Pages record. The apt repository and the README use
`https://mith.ro/uspiflash/`, as spiflash's does; if HTTPS is still not
serving once `publish-apt` has run, check the API again and fix this doc.

### 4. Read the Docs

Tim imports `mithro/uspiflash` at
<https://app.readthedocs.org/dashboard/import/>: project slug `uspiflash`,
default branch `main`. "Include Git LFS objects in archives" is a UI-only
setting Tim leaves as found. Once imported, <https://uspiflash.readthedocs.io/>
builds from [`.readthedocs.yaml`](https://github.com/mithro/uspiflash/blob/main/.readthedocs.yaml)
on every push, same as the `sphinx` job in `docs.yml` checks in CI.

## A data update

A `spiflash` version bump is a commit like any other. Refresh `uv.lock` to the
latest release without pinning an exact version:

```sh
uv lock --upgrade-package spiflash
```

Raise the minimum only when a change actually needs it, by editing the `>=`
bound in `pyproject.toml`'s `dependencies` — never an exact `==` pin, which
would contradict the `>=` policy and `debian/control`'s own bound. When the
minimum changes, also bump both `python3-spiflash (>= …~)` bounds in
`debian/control` (keeping the trailing `~`) to match. Review, commit, merge.
The next green run publishes it.

## Verifying a release

- PyPI: <https://pypi.org/project/uspiflash/> shows the new `X.Y.postN`.
- apt: `sudo apt update && apt-cache policy python3-uspiflash` on a machine
  set up per <https://mith.ro/uspiflash/> shows the same version.
- The signing key: `curl -fsS https://mith.ro/uspiflash/uspiflash.gpg | gpg
  --show-keys` shows the fingerprint above.
