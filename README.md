# TorrServer DSM

Synology DSM package for [TorrServer](https://github.com/YouROK/TorrServer).

TorrServer DSM provides a native DSM interface for managing TorrServer on Synology NAS.

## Features

- DSM application (the **Helper**) for managing the package, available in
  English, Russian, Ukrainian, Lithuanian and Polish
- Port configuration for HTTP / HTTPS, Force HTTPS
- TorrServer cache folder and optional FUSE
- SSL certificates: TorrServer's own, or taken from DSM / a manual path
- HTTP authentication
- Logs and package status
- Restart TorrServer from DSM
- Works out of the box, no root access needed for everyday use
  (see [Folder access and optional permissions](#folder-access-and-optional-permissions))

## Requirements

- Synology DSM 7.3 or newer (verified on DSM 7.4.1)
- A DSM **administrator** account to open the Helper
- Supported architectures:
  - `amd64` (Intel / AMD, `x86_64`)
  - `arm64` (`aarch64`)
  - `arm7` (`armv7`)

## Installation

1. Download the `.spk` for your architecture from the
   [Releases](https://github.com/vladlenas/TorrServer-DSM/releases) page, or add
   the package source below.
2. DSM **Package Center → Manual Install**, select the file.
3. Open **TorrServer DSM** from the DSM main menu and choose the cache folder
   with the **Browse** button.
4. TorrServer's own web interface is at `http://<NAS address>:8090` (the port
   can be changed in the Helper).

### Automatic update

Add this source to your Synology NAS Package Center:

    https://ggrigi.lt

## Folder access and optional permissions

**Nothing needs to be set up for a normal install.** You can change the port,
the password, HTTPS with the built-in certificate and FUSE right away.

The only thing the Helper needs is a folder for the cache. If the service user
may write there, the Helper creates `Cache` and `FUSE` itself. If it may not,
it tells you how to fix that the standard DSM way:

> Control Panel → Shared Folder → select the folder → Edit → Permissions →
> **System internal user** → give **TorrServer** *Read/Write*.

Some things need root and are therefore **optional**. Without the permission
below they are simply unavailable and everything else keeps working:

- restarting TorrServer from the Helper (restart it from DSM Package Center
  instead),
- certificates taken from DSM or from a manual path,
- creating `Cache` / `FUSE` in a folder the service user cannot write to.

To enable them, open **DSM Task Scheduler**, create a **User-defined script**
task, select **root** as the user, and run once:

    /var/packages/TorrServer/scripts/setup-permissions

The Helper shows the same instruction in a separate window and can check
whether the permission is configured. Package scripts do not run as root, so
the rule is not removed on uninstall. Remove it with:

    sudo rm -f /etc/sudoers.d/TorrServer

## Upgrading

Settings are kept across upgrades. On every upgrade the package removes
leftovers from older versions (obsolete files, `*.tmp` files and, for
the self-signed certificate mode, a stale `server.pem` / `server.key`). To
start from defaults, tick **Reset package settings to defaults** in the upgrade
wizard. Torrents and TorrServer's own database are not touched by the reset.

After upgrading, reload the DSM page (**Ctrl+Shift+R**) so the browser picks up
the new application files.

The optional sudo rule is written once and is **not** refreshed by an upgrade.
If you enabled it with a version older than the one that introduced
`prepare-directory`, run `setup-permissions` again; until then the Helper treats
the optional features as unavailable.

## Security

- The Helper listens on `127.0.0.1:42777` only and is reached through DSM nginx
  (`/webman/3rdparty/TorrServer/helper/`). **nginx does not check the DSM login
  for that path**, so the Helper verifies the session itself: it asks DSM's
  `authenticate.cgi` who the caller is and serves **DSM administrators only**.
  Everything else gets `403`, and it fails closed (if the check cannot be
  performed, nobody gets in). The reason for a refusal is written to
  `service.log` (`helper-auth: ...`). Never expose port 42777.
- State-changing requests are accepted only from the same origin (CSRF guard).
- Directories and certificate paths must be under `/volumeN/` and must not
  contain `..` or point through symbolic links. The TorrServer directory must
  not contain spaces.
- Passwords are stored by TorrServer in `accs.db` (mode `0600`); other
  TorrServer accounts in that file are preserved.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| The Helper window is blank | Reload DSM with **Ctrl+Shift+R**. If it stays blank, open the browser console (F12) and look for lines starting with `[TorrServer]`. |
| "Access denied" in the Helper | Sign in to DSM as an administrator. If you are one, see the reason: `sudo grep helper-auth /var/packages/TorrServer/var/service.log \| tail`. |
| "The TorrServer service user cannot write to this folder" | Give the **TorrServer** user Read/Write on the shared folder (see above). |
| "sudo: a password is required" or "DSM permissions are missing or out of date" | Only needed for the optional features: run `setup-permissions` again (see above). |
| TorrServer is not reachable | Check the Logs tab (`TorrServer.log`, `service.log`), then restart the package from DSM Package Center. |

Logs: `TorrServer.log` (TorrServer's own) and `service.log` (service output,
Helper messages) are in `/var/packages/TorrServer/var/` and in the Helper's
**Logs** tab.

## Development

### Building

Clone the repository:

    git clone https://github.com/vladlenas/TorrServer-DSM.git
    cd TorrServer-DSM

Build the SPK packages (all architectures, or one, e.g. `make torrserver-amd64`):

    make

The generated packages are placed in the `spk` directory. To clean the build
directory:

    make clean

### Versions and releases

The TorrServer version used by the package and the package version are defined
in `Makefile` (`TORRSERVER_VERSION`, `PKG_VERSION`). Downloaded binaries are
cached per TorrServer version in `dest_bin/`.

`PKG_VERSION` is `<package version>.<TorrServer build>`. For example
`2.3.145.2` is version `2.3` of this package shipping TorrServer build
`145.2` (`TORRSERVER_VERSION := MatriX.145.2`). Raise the package part
(`2.3`) for every release of the package; the TorrServer part (`145.2`) changes
only together with `TORRSERVER_VERSION`. A test checks that the two agree.

To publish a release:

1. Bump `PKG_VERSION` in `Makefile`.
2. Add a section for that version at the **top** of `CHANGELOG.md`
   (`## <version> (<date>)`). Its text becomes the release notes.
3. Merge to `main`. CI runs the tests, builds the `.spk` files for all
   architectures and publishes the GitHub release `v<version>`.

A test fails if the top `CHANGELOG.md` entry does not match `PKG_VERSION`.

### Checksums

Downloaded inputs (TorrServer and ffprobe) can be pinned in `checksums.sha256`.
Generate the sums once, review them against the upstream release pages and
commit the file:

    make checksums

From then on a build refuses a download whose SHA-256 differs, and CI refuses
downloads that are not pinned. Pins are keyed by version, so run
`make checksums` again after changing `TORRSERVER_VERSION` (delete `dest_bin`
first if the binaries are already cached).

### Translations

The Helper's texts live in `src/helper/locales/<language>.json`; the English
text is the key. Tests enforce these rules:

- **Names of DSM's own screens follow DSM.** DSM ships Russian and Polish, so
  those two use DSM's official wording (for example Russian «Планировщик
  задач», Polish „Harmonogram zadań"). DSM has no Ukrainian or Lithuanian
  interface, so there the names stay in English exactly as DSM shows them
  (Control Panel → Task Scheduler …).
- **Every message the code can show has a translation** in all four languages.
  Messages are translated as whole sentences, so a value goes last
  (`Web port is already in use: 8090`) and a message contains no quotes.
- Messages name this package's own buttons and pages exactly as the interface
  does (for example the translated "Browse" button).

When you add or change a message, update all five files; the tests list what
is missing.

### Tests

No DSM is needed:

    python3 -m unittest discover -s tests -v   # helper, documentation checks
    node tests/test_ui.js                      # DSM desktop app (src/ui/TorrServer.js)
    sh tests/test_scripts.sh                   # package scripts, upgrade migration
    bash tests/test_build.sh                   # checksum handling in build-package.sh

CI runs all of them for every pull request and before every release.

## Links

- [TorrServer Project](https://github.com/YouROK/TorrServer)
- [TorrServer DSM](https://github.com/vladlenas/TorrServer-DSM)
- [Support TorrServer Project](https://github.com/YouROK/TorrServer#donate)

## Credits

TorrServer by [YouROK](https://github.com/YouROK/TorrServer).

Synology SPK package maintained by [vladlenas](https://github.com/vladlenas).
