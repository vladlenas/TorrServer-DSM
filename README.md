# TorrServer DSM

Synology DSM package for [TorrServer](https://github.com/YouROK/TorrServer).

TorrServer DSM provides a native DSM interface for managing TorrServer on Synology NAS.

## Features

- DSM application (the **Helper**) for managing the package, available in
  English, Russian, Ukrainian, Lithuanian and Polish
- Port configuration for HTTP / HTTPS, Force HTTPS
- TorrServer cache folder and optional FUSE
- HTTPS: TorrServer's own certificate, or one of your own uploaded on TorrServer's
  page, kept fresh by a DSM task or a reverse proxy (see [SSL certificates](#ssl-certificates))
- HTTP authentication
- Logs and package status
- Restart TorrServer from the Helper
- Runs with the reduced rights DSM gives a package (its own `TorrServer` user):
  nothing in the package runs as root, and there is no sudo rule
  (see [Folder access](#folder-access))

## Requirements

- Synology DSM 7.3 or newer (verified on DSM 7.4.1)
- A DSM **administrator** account to open the Helper
- Python 3.7 or newer for the Helper. DSM 7 includes it; if it is missing on your
  system, install **Python 3** from DSM Package Center and restart the package
  (the log says so: `Python 3 was not found`)
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

## Folder access

**Nothing needs to be set up for a normal install.** You can change the port,
the password, HTTPS with the built-in certificate and FUSE right away.

The package runs as its own unprivileged DSM user, **TorrServer**, as DSM
intends for packages. Nothing in it runs as root.

The TorrServer folder is optional. Leave it empty and TorrServer keeps its
data where it already is; the disk cache is then switched on in the TorrServer
web interface. Choose a folder only if you want the Helper to prepare `Cache`
(and `FUSE`) for you. Ticking **FUSE** shows a short inline hint on using it
with Plex or Emby; there is no separate recommendations window.

If the **TorrServer** user may write there, the Helper creates `Cache` and
`FUSE` itself. The folder chooser marks folders it cannot write to with
"no write access" and warns before you save. If you save such a folder anyway,
the Helper names it and the shared folder to fix, the standard DSM way:

> Control Panel → Shared Folder → select the folder → Edit → Permissions →
> **System internal user** → give **TorrServer** *Read/Write*.

### When TorrServer is stopped

The Status page shows the last lines of the log (usually the reason, for
example a port that is already in use) and a **Start** button.

## SSL certificates

HTTPS is switched on in the Helper (**Settings → HTTPS**). The certificate
itself is set on TorrServer's own web page. The package runs without root, so
it cannot read DSM's certificate store and does not copy certificates for you.
The **SSL Certificate** card in the Helper's Settings page is a short manual for
what follows.

**Default.** Nothing to do. TorrServer makes a self-signed pair
(`server.pem`, `server.key` in `/var/packages/TorrServer/var/`) when none is
there, and browsers warn about it.

**Manual upload.** Turn on HTTPS in the Helper, save and restart. Then, on
TorrServer's web page, open **Settings → Additional → HTTPS** (PRO mode; the
card is shown only while HTTPS is on, TorrServer 146 or newer) and upload a PEM
certificate chain and an unencrypted key, or point TorrServer to files it can
read. An upload is copied to `ssl/uploaded.crt` and `ssl/uploaded.key` in the
data folder and the choice is kept in TorrServer's own settings database, so it
survives restarts. For example, export the certificate in DSM (**Control Panel →
Security → Certificate → Action → Export certificate**) and upload
`fullchain.pem` and `privkey.pem` from the archive. A certificate uploaded this
way is **not renewed by itself**: upload it again after each renewal, or use one
of the two options below.

**Option 1: reverse proxy (recommended).** Let DSM provide HTTPS and renew the
certificate: **Control Panel → Login Portal → Advanced → Reverse Proxy**, add a
rule from an HTTPS address of your choice to `http://localhost:<TorrServer
port>`, assign your certificate to that rule in **Control Panel → Security →
Certificate → Settings**, and keep HTTPS in TorrServer switched off.

**Option 2: Task Scheduler.** Keep DSM's certificate up to date for TorrServer
with a scheduled task. In **Control Panel → Task Scheduler** create a
**Scheduled Task → User-defined script**, user **root**, repeated daily, with
this script (it is also shown in the Helper):

```sh
#!/bin/sh
ARCHIVE=/usr/syno/etc/certificate/_archive
ID=$(cat "$ARCHIVE/DEFAULT")
DEST=/volume1/certs

mkdir -p "$DEST"
for f in fullchain.pem privkey.pem; do
    cp "$ARCHIVE/$ID/$f" "$DEST/$f.tmp"
    chown TorrServer "$DEST/$f.tmp"
    chmod 600 "$DEST/$f.tmp"
    mv "$DEST/$f.tmp" "$DEST/$f"
done
```

- `DEST` is a folder of your choice. The **TorrServer** user needs access to it
  (see [Folder access](#folder-access)); it can be a folder inside a shared
  folder.
- `DEFAULT` holds the ID of the certificate DSM uses by default. If your
  certificate is for a domain and is not the default one, put its ID into the
  script instead. The IDs are the folder names in
  `/usr/syno/etc/certificate/_archive`.
- Then, on TorrServer's web page, set the certificate and the key to
  `<DEST>/fullchain.pem` and `<DEST>/privkey.pem` by file path (not upload).
  TorrServer re-reads files given by path, so a renewed certificate is picked up
  without a restart.
- Run the task once by hand after creating it and check that the two files
  exist. The script is a template: the layout of DSM's certificate folder can
  differ between DSM versions.

TorrServer's own messages about HTTPS are in `TorrServer.log`.

## Upgrading

Settings are kept across upgrades. On every upgrade the package removes
leftovers from older versions (obsolete files and `*.tmp` files). To
start from defaults, tick **Reset package settings to defaults** in the upgrade
wizard. Torrents and TorrServer's own database are not touched by the reset.

After upgrading, reload the DSM page (**Ctrl+Shift+R**) so the browser picks up
the new application files.

**Upgrading to 2.8 (no root).** Version 2.8 removes `certificate-helper`,
`prepare-directory` and `setup-permissions`, and the helper's certificate
source setting. **Recommended:** if you ever enabled the optional permissions
(a Task Scheduler task running `setup-permissions`), delete the sudo rule they
created. It is unused now, and the package cannot remove it because it does
not run as root. Run once, in SSH:

    sudo rm -f /etc/sudoers.d/TorrServer

If you used **DSM certificate** or **Manual paths** in the Helper, the copied
`server.pem` / `server.key` stay in place and keep working, but nothing renews
them any more. Switch to option 1 or 2 above before the certificate expires.
To go back to a self-signed certificate, delete `server.pem` and `server.key`
in `/var/packages/TorrServer/var/` and restart TorrServer, or upload a
certificate on TorrServer's page.

## Security

- The Helper listens on `127.0.0.1:42777` only and is reached through DSM nginx
  (`/webman/3rdparty/TorrServer/helper/`). **nginx does not check the DSM login
  for that path**, so the Helper verifies the session itself: it asks DSM's
  `authenticate.cgi` who the caller is and serves **DSM administrators only**.
  Everything else gets `403`, and it fails closed (if the check cannot be
  performed, nobody gets in). The reason for a refusal is written to
  `TorrServer.log` (`helper-auth: ...`). Never expose port 42777.
- State-changing requests are accepted only from the same origin (CSRF guard).
- No root: the package runs as the `TorrServer` user and installs no sudo rule.
  If an older version left `/etc/sudoers.d/TorrServer`, remove it with
  `sudo rm -f /etc/sudoers.d/TorrServer`.
- The TorrServer directory must be under `/volumeN/`, must not contain `..`
  or spaces, and must not point through symbolic links.
- Passwords are stored by TorrServer in `accs.db` (mode `0600`); other
  TorrServer accounts in that file are preserved.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| The Helper window is blank | Reload DSM with **Ctrl+Shift+R**. If it stays blank, open the browser console (F12) and look for lines starting with `[TorrServer]`. |
| "Access denied" in the Helper | Sign in to DSM as an administrator. If you are one, see the reason: `sudo grep helper-auth /var/packages/TorrServer/var/TorrServer.log \| tail`. |
| "The TorrServer service user cannot write to /volumeN/…" | The message names the folder and the shared folder to fix. Give the **TorrServer** user Read/Write on that shared folder (see above). The folder chooser already marks such folders with "no write access" and warns before you save. |
| HTTPS shows a certificate warning | The self-signed default is in use. Upload a certificate on TorrServer's page or use a reverse proxy (see [SSL certificates](#ssl-certificates)). |
| A folder cannot be opened (not even in File Station) after FUSE was used | A FUSE mount was left behind when TorrServer ended without releasing it (for example it was killed while Plex or Docker still used the folder). The package removes such mounts every time it starts, restarts or stops TorrServer; to do it by hand, as root: `grep fuse.torrserver /proc/mounts`, then `umount -l <mount point>`. |
| TorrServer is not reachable | Check the Logs tab, then restart the package from DSM Package Center. |

Logs: everything goes to one file, `TorrServer.log`, in
`/var/packages/TorrServer/var/` and in the Helper's **Logs** tab. TorrServer,
the start/stop scripts (`service:`, `restart-torrserver:`) and the Helper write
to it in the same format. The
file is never wiped when the service starts, so what happened before a crash is
still there afterwards, and you can read or download it while TorrServer is
stopped. It is rotated at 2 MB (`TorrServer.log.1`, `.2`). Older versions
also kept `service.log` and `Helper.log`; an upgrade removes them.

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
3. Pin the downloads (see *Checksums*) and commit.
4. Run `sh .github/scripts/release-check.sh`. It refuses a version that is not
   newer than the latest release, a tag that already exists (also on GitHub),
   a changelog that does not match, downloads that are not pinned, uncommitted
   changes and failing tests.
5. Merge to `main`. CI runs the tests, builds the `.spk` files for all
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
