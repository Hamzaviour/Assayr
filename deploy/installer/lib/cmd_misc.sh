# shellcheck shell=bash
# Day-to-day commands for an installation.

usage() {
  cat <<'EOF'
Assayr installer and administration

From an unpacked bundle:
  install        Install Assayr (asks a few questions; see README-INSTALL.md)
                   --dir DIR  --license FILE  --http  --https-port N  --http-port N  --non-interactive
  upgrade        Upgrade an installation to this bundle's version (backs up first, rolls back on failure)
                   --dir DIR

From the installation folder (or with --dir DIR):
  status         Version, address, services and free disk
  backup         Back up the database, evidence files and settings   --to DIR
  restore        Replace all data with a backup                      FILE [--yes]
  start          Start Assayr
  stop           Stop Assayr
  restart        Restart Assayr (after changing assayr.env or the certificate)
  logs           Follow the logs                                     [SERVICE]
  create-admin   Create another administrator account
  uninstall      Stop and remove the containers; --delete-data also deletes all data
  version        Show the version
  help           Show this help
EOF
}

cmd_version() {
  echo "Assayr $(bundle_value "$SCRIPT_DIR" VERSION || echo unknown) ($(bundle_value "$SCRIPT_DIR" ARCH || echo unknown))"
}
