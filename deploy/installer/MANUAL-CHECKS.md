# Manual checks on Docker Desktop (macOS and Windows)

GitHub's macOS and Windows runners can't run Docker, so these are checked by hand before the
first release to clients and whenever anything under `deploy/` changes. Use the bundles from the
release workflow's artifacts (run it by hand with a version) or from a release.

Record the date, the Assayr version, the machine and the result of each line in the release notes
or the pull request.

## macOS (Apple Silicon: arm64 bundle; Intel: amd64 bundle)

- [ ] Docker Desktop running with at least 6 GB of memory.
- [ ] `./assayr install` with the defaults (self-signed certificate) finishes and prints `https://localhost`.
- [ ] The browser opens `https://localhost` after accepting the warning; sign in works.
- [ ] Upload a small PDF to A.5.1; it leaves "verifying" within a minute.
- [ ] `./assayr backup`, then `./assayr restore <file>` (type `restore`) finish without errors.
- [ ] `./assayr status` shows every service running and "Application: ready".
- [ ] Turn Wi-Fi off, `./assayr restart`: Assayr comes back and evidence verification still works (ClamAV offline).
- [ ] `./assayr uninstall --delete-data` (type `delete`) removes `~/assayr` and the containers.

## Windows 11 (amd64 bundle, Docker Desktop with WSL2 and Ubuntu)

- [ ] WSL integration on for Ubuntu; in Ubuntu, `docker info` works.
- [ ] The bundle copied into the Ubuntu home folder (not `/mnt/c/...`), then `./assayr install` finishes.
- [ ] Windows browser opens `https://localhost`; sign in works.
- [ ] Evidence upload verified; backup and restore work; status is ready.
- [ ] Restart Windows, start Docker Desktop: Assayr comes back on its own (restart policy).
- [ ] `./assayr uninstall --delete-data` removes everything.
