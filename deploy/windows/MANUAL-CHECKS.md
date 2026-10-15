# Windows installer: manual checks before each release

The release workflow tests a silent install, evidence upload, backup/restore, upgrade, rollback and
uninstall on Windows Server 2022. These checks cover what it cannot.

## Windows Server 2019 VM (no hosted runner exists)

- [ ] Interactive install with a self-signed certificate; the browser opens the sign-in page.
- [ ] Install with a `.pfx` certificate and its password.
- [ ] With IIS running on port 443, the wizard names the program using the port and accepts 8443.
- [ ] Reboot the server: all five Assayr services come back and the site answers.
- [ ] Task Scheduler shows "Assayr nightly backup" at 02:00 running as SYSTEM.
- [ ] Start menu: Open Assayr, Assayr Admin and Back up now work.
- [ ] Uninstall keeping the data, reinstall, sign in with the same account.
- [ ] Uninstall deleting the data: `C:\ProgramData\Assayr` is gone.

## Any Windows version

- [ ] SmartScreen behaviour for the downloaded exe (unsigned: "More info > Run anyway").
- [ ] The wizard pages read well at 100% and 150% display scaling.

## Turning on code signing

1. Buy an OV or EV code-signing certificate and export it as a `.pfx`.
2. Add two repository secrets: `WINDOWS_SIGNING_CERT` (the `.pfx` as base64:
   `[Convert]::ToBase64String([IO.File]::ReadAllBytes("cert.pfx"))`) and `WINDOWS_SIGNING_PASSWORD`.
3. The release workflow's Sign step then signs `Assayr-Setup-<version>.exe`. To sign the uninstaller
   too, pass `/DSignTool=...` to ISCC with a configured sign tool (see the Inno Setup `SignTool` docs).

## Clean server without the Visual C++ runtime

- [ ] On a fresh Windows Server 2022 VM **without** the VC++ 2015-2022 redistributable, the install succeeds (PostgreSQL uses the runtime DLLs bundled in `pgsqlin`).
