# Installing Assayr on Windows Server

Assayr runs on your own Windows server as a set of Windows services. The installer contains
everything it needs (database, web server, malware scanner): no internet access, Docker or WSL is
needed to install or run it, and nothing is sent outside your network.

## What you need

- Windows Server 2019, 2022 or 2025 (64-bit). Windows 10/11 work for evaluation.
- 4 CPU cores, 8 GB of memory (16 GB recommended), 100 GB of free disk for the data folder.
- Ports 443 and 80 free, or choose others in the wizard.
- An administrator account on the server.

## 1. Download and check the file

Download `Assayr-Setup-<version>.exe` and `SHA256SUMS.txt` from the release page. On the server,
in PowerShell, compare the checksum with the one in `SHA256SUMS.txt`:

```powershell
Get-FileHash .\Assayr-Setup-0.3.0.exe -Algorithm SHA256
```

For a server without internet access, check the file on another computer and copy it across by
your usual means (USB drive, internal file transfer).

Until the installer is code-signed, Windows SmartScreen may say "Windows protected your PC". Click
**More info**, then **Run anyway**.

## 2. Install

Run `Assayr-Setup-<version>.exe` as an administrator. The wizard asks for:

1. **Server**: the hostname users type in the browser (for example `grc.example.local`), your
   organisation name and the HTTPS and HTTP ports. If a port is taken (by IIS, for example), the
   wizard names the program using it.
2. **HTTPS certificate**: create a self-signed certificate (browsers warn until you replace it),
   use a `.crt` and `.key` from your certificate authority, or use a `.pfx` file.
3. **First administrator**: email and a password of at least 12 characters.
4. **Malware scanning**: on by default; turning it off saves about 2 GB of memory.
5. **Data folder**: `C:\ProgramData\Assayr` by default; choose another drive if you prefer.

Setup installs Assayr to `C:\Program Files\Assayr`, starts it and opens `https://<hostname>`.
Sign in with the administrator account.

## Day to day

Use **Assayr Admin** from the Start menu (or `"C:\Program Files\Assayr\assayr-admin.cmd"` in an
administrator command prompt):

| Command | What it does |
|---|---|
| `assayr-admin status` | Version, address, services, free disk |
| `assayr-admin start` / `stop` / `restart` | Start, stop or restart Assayr |
| `assayr-admin logs api` | Show a service's log (`api`, `worker`, `web`, `db`, `clamav`) |
| `assayr-admin backup` | Back up the database, evidence files and settings |
| `assayr-admin restore FILE` | Replace all data with a backup (takes a safety backup first) |
| `assayr-admin create-admin --email EMAIL` | Create another administrator |
| `assayr-admin update-signatures PATH` | Update the malware signatures from a `.cvd`/`.cld` file or folder |

Assayr runs as five Windows services (Assayr Database, Assayr ClamAV, Assayr API, Assayr Worker,
Assayr Web) that start automatically with Windows.

## Backups

A backup runs every night at 02:00 (Task Scheduler, "Assayr nightly backup"); the newest 14 are
kept in `<data folder>\backups`. Copy them to another machine regularly. A backup contains the
database password and the HTTPS private key: keep backups where only administrators can read them.

Backups are the same format on Windows and Linux, so you can move between them: install Assayr on
the new server, copy a backup across and run `assayr-admin restore FILE`.

## HTTPS certificate

To replace the certificate: put the certificate (with any intermediate certificates after it) in
`<data folder>\certs\tls.crt` and its key in `tls.key`, then run `assayr-admin restart`.

## Malware signatures

The installer contains the virus signatures current at release time. To update them on a server
without internet access, download `main.cvd`, `daily.cvd` and `bytecode.cvd` on another computer and
run `assayr-admin update-signatures <folder>`.

## Antivirus on the server

If the server runs Microsoft Defender or another antivirus, exclude `C:\Program Files\Assayr` and the
data folder. Otherwise the antivirus may lock database files or quarantine uploaded evidence before
Assayr's own scanner reports on it.

## Upgrading

Run the newer `Assayr-Setup-<version>.exe` on the same server. It takes a backup, installs the new
version and starts it. If the new version does not start, it puts the previous version and its data
back automatically and tells you so.

## Unattended install

Copy `answers.example.ini`, fill it in, and run (the password comes from an environment variable,
never from the file or the command line):

```powershell
$env:ASSAYR_ADMIN_PASSWORD = Read-Host -AsSecureString "Administrator password" |
  ForEach-Object { [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($_)) }
.\Assayr-Setup-0.3.0.exe /VERYSILENT /SUPPRESSMSGBOXES /CONFIG=C:\path\answers.ini
Remove-Item Env:\ASSAYR_ADMIN_PASSWORD
```

The exit code is 0 on success. For a `.pfx` certificate, put its password in `ASSAYR_PFX_PASSWORD`.

## Uninstall

Use **Settings > Apps > Assayr > Uninstall**. The services, program files and firewall rules are
removed; the data folder is kept unless you choose to delete it. Silent uninstall:
`"C:\Program Files\Assayr\unins000.exe" /VERYSILENT` (add `/DELETEDATA=yes` to delete the data too).

## Troubleshooting

Every installer and admin action is written to `<data folder>\install.log` (passwords never are).
`assayr-admin status` and `assayr-admin logs api` are the first things to check.
