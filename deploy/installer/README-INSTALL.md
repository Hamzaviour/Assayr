# Installing Assayr

Assayr runs on your own server. Everything it needs is in this bundle: no internet access is
needed to install or run it.

| Where | Use |
|---|---|
| Linux server (x86-64 or arm64) | Production |
| macOS with Docker Desktop or Colima | Evaluation only |
| Windows 10/11 with Docker Desktop and WSL2 | Evaluation only |
| Windows Server 2019/2022/2025 | Production: use `Assayr-Setup-<version>.exe` instead (see README-INSTALL-WINDOWS.md) |

## What you need

- Docker Engine 24 or newer with the Compose plugin (2.17 or newer). On macOS and Windows, Docker Desktop.
- 4 CPU cores, 8 GB of memory (16 GB recommended), 100 GB of free disk.
- Ports 443 and 80 free (or choose others with `--https-port` and `--http-port`).
- `openssl`, unless you bring your own certificate (it is installed on almost every system).
- The right bundle for the machine: `linux-amd64` for Intel/AMD servers, Windows PCs and Intel Macs;
  `linux-arm64` for Apple Silicon Macs (M1–M4) and arm64 servers.

## 1. Check the download

Compare the checksum with the one published on the release page (or sent to you separately):

```bash
sha256sum assayr-0.2.0-linux-amd64-offline.tar.gz      # Linux and WSL
shasum -a 256 assayr-0.2.0-linux-amd64-offline.tar.gz  # macOS
```

For a server without internet access, copy the file across by your usual means (USB drive,
internal file transfer) after checking it.

## 2. Install

### Linux (production)

```bash
tar -xzf assayr-0.2.0-linux-amd64-offline.tar.gz
cd assayr-0.2.0
sudo ./assayr install
```

The installer checks the machine and the bundle, then asks for:

- the **hostname** users will type in the browser (for example `grc.example.local`);
- your **organisation name**;
- an **HTTPS certificate** and key from your certificate authority — or press Enter and it creates a
  self-signed certificate (browsers warn about it until you replace it);
- the **first administrator's** email and password (at least 12 characters).

It installs to `/opt/assayr`, starts Assayr and prints the address. Open it in a browser and sign in.

### macOS (evaluation)

1. Install and start Docker Desktop (Settings > Resources: give it at least 6 GB of memory).
2. In Terminal:
   ```bash
   tar -xzf assayr-0.2.0-linux-arm64-offline.tar.gz   # amd64 on an Intel Mac
   cd assayr-0.2.0
   ./assayr install
   ```
3. Open `https://localhost` and accept the certificate warning.

It installs to `~/assayr`.

### Windows (evaluation)

1. Install Docker Desktop with the WSL 2 backend, and Ubuntu from the Microsoft Store.
2. In Docker Desktop, Settings > Resources > WSL integration: turn it on for Ubuntu.
3. Open **Ubuntu** from the Start menu, copy the bundle into your Linux home folder, and run:
   ```bash
   tar -xzf assayr-0.2.0-linux-amd64-offline.tar.gz
   cd assayr-0.2.0
   ./assayr install
   ```
4. Open `https://localhost` in your Windows browser and accept the certificate warning.

It installs to `~/assayr` inside Ubuntu.

### Install without questions

Give every answer as an environment variable and add `--non-interactive`. Read the
administrator password into the environment first, so it never appears on a command line, in
the process list or in your shell history:

```bash
read -r -s -p "Administrator password: " ASSAYR_ADMIN_PASSWORD; echo
export ASSAYR_ADMIN_PASSWORD
sudo --preserve-env=ASSAYR_ADMIN_PASSWORD \
  ASSAYR_HOSTNAME=grc.example.local ASSAYR_ORG_NAME="Example Bank" \
  ASSAYR_ADMIN_EMAIL=isms@example.com \
  ASSAYR_TLS_CERT=/root/grc.crt ASSAYR_TLS_KEY=/root/grc.key \
  ./assayr install --non-interactive
unset ASSAYR_ADMIN_PASSWORD
```

On macOS and in WSL, where the install doesn't use `sudo`, run the same command without
`sudo --preserve-env=ASSAYR_ADMIN_PASSWORD`. Leave out `ASSAYR_TLS_CERT` and `ASSAYR_TLS_KEY` for a self-signed certificate. Other options:
`--dir DIR` (another install folder, new or empty; one installation per machine), `--license FILE`, `--https-port N`, `--http-port N`,
`ASSAYR_MALWARE_SCAN=false` (no ClamAV; saves about 2 GB of memory), and `--http` (plain HTTP on
port 8080 for evaluation, or behind your own HTTPS proxy — set `ASSAYR_BEHIND_TLS_PROXY=yes` then).

## Day to day

Run these from the install folder (`/opt/assayr`, with `sudo`, on Linux; `~/assayr` elsewhere):

| Command | What it does |
|---|---|
| `./assayr status` | Version, address, services, free disk |
| `./assayr backup` | Back up the database, evidence files and settings to `backups/` |
| `./assayr restore FILE` | Replace all data with a backup (takes a safety backup first) |
| `./assayr stop` / `start` / `restart` | Stop, start or restart Assayr |
| `./assayr logs [api\|worker\|web\|db]` | Follow the logs |
| `./assayr create-admin` | Create another administrator (for example when one forgot their password) |
| `./assayr uninstall` | Stop and remove the containers; data stays. `--delete-data` removes everything |

## HTTPS certificate

To replace the self-signed certificate: put your certificate (with any intermediate certificates
after it) in `certs/tls.crt` and its key in `certs/tls.key` inside the install folder, then run
`./assayr restart`.

## Backups

Back up regularly, for example every night with cron (`0 2 * * * /opt/assayr/assayr backup`), and
copy the files in `backups/` to another machine. A backup contains the database password and the
HTTPS private key: keep backups where only administrators can read them.

To move Assayr to a new server: install the same version there, copy a backup across, and run
`./assayr restore FILE`.

## Upgrading

Unpack the new bundle anywhere and run its `upgrade` command:

```bash
tar -xzf assayr-0.3.0-linux-amd64-offline.tar.gz
cd assayr-0.3.0
sudo ./assayr upgrade
```

It backs up first, then installs the new version. If the new version doesn't start, it puts the
previous version and your data back automatically and tells you so.

## Troubleshooting

Every command writes what it did to `install.log` in the install folder (no passwords are ever
written there). `./assayr status` and `./assayr logs api` are the first things to check.
