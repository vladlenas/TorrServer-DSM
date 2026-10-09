# TorrServer DSM

Synology DSM package for [TorrServer](https://github.com/YouROK/TorrServer).

TorrServer DSM provides a native DSM interface for managing TorrServer on Synology NAS.

## Features

- DSM application (the **Helper**) for managing the package, available in
  English, Russian, Ukrainian, Lithuanian and Polish
- Port configuration for HTTP / HTTPS, Force HTTPS
- TorrServer cache folder and optional FUSE
- SSL certificates: TorrServer's own, or taken from DSM; a certificate of your own
  is uploaded on TorrServer's page (see [SSL certificates](#ssl-certificates))
- HTTP authentication
- Logs and package status
- Restart TorrServer from the Helper (no root needed)
- Works out of the box, no root access needed for everyday use
  (see [Folder access and optional permissions](#folder-access-and-optional-permissions))

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

## Folder access and optional permissions

**Nothing needs to be set up for a normal install.** You can change the port,
the password, HTTPS with the built-in certificate and FUSE right away.

The TorrServer folder is optional. Leave it empty and TorrServer keeps its
data where it already is; the disk cache is then switched on in the TorrServer
web interface. Choose a folder only if you want the Helper to prepare `Cache`
(and `FUSE`) for you. Ticking **FUSE** shows a short inline hint on using it
with Plex or Emby; there is no separate recommendations window.

If the service user
may write there, the Helper creates `Cache` and `FUSE` itself. If it may not,
it tells you how to fix that the standard DSM way:

> Control Panel → Shared Folder → select the folder → Edit → Permissions →
> **System internal user** → give **TorrServer** *Read/Write*.

Restarting TorrServer from the Helper works without root. A few things do need
root and are therefore **optional**. Without the permission below they are
simply unavailable and everything else keeps working:

- certificates taken from DSM,
- creating `Cache` / `FUSE` in a folder the service user cannot write to.

To enable them, open **DSM Task Scheduler**, create a **User-defined script**
task, select **root** as the user, and run once:

    /var/packages/TorrServer/scripts/setup-permissions

The Helper shows the same instruction inside the **SSL Certificate** card on
the Settings page and can check whether the permission is configured. Package
scripts do not run as root, so the rule is not removed on uninstall. Remove it
with:

    sudo rm -f /etc/sudoers.d/TorrServer

### When TorrServer is stopped

The Status page shows the last lines of the log (usually the reason, for
example a port that is already in use) and a **Start** button. Starting needs
no root either.

## SSL certificates

HTTPS is switched on in the Helper (**Settings → HTTPS**). Which certificate
TorrServer then serves depends on where it comes from. All files are in the
package data folder, `/var/packages/TorrServer/var/`.

| Source | Where you set it | Files | Renewal |
| --- | --- | --- | --- |
| TorrServer's own, self-signed (default) | Helper, **TorrServer self-signed** | `server.pem`, `server.key`, made by TorrServer | TorrServer renews it itself; browsers warn about it |
| A DSM certificate (for example Let's Encrypt for your domain) | Helper, **DSM certificate** | `server.pem`, `server.key`, copied from DSM | copied again at every start or restart of TorrServer |
| A certificate of your own (TorrServer 146 or newer) | TorrServer's web page: **Settings → Additional → HTTPS** (PRO mode, shown only while HTTPS is on) | `ssl/uploaded.crt`, `ssl/uploaded.key` | no restart needed; you upload it again when it expires |

**Self-signed.** Nothing to do. TorrServer makes the pair when it is missing and
makes a new one before it expires.

**DSM certificate.** Needs the optional permission (see
[Folder access and optional permissions](#folder-access-and-optional-permissions)),
because TorrServer's service user cannot read DSM's certificates. Choose the
certificate in the Helper and save. `certificate-helper` (it runs as root through
sudo, and only reads DSM's certificate folder, `/usr/syno/etc/certificate`) copies the chosen
certificate and key to `server.pem` and `server.key`, owned by the service user
(the key readable by it only). The copy is made when TorrServer starts or is
restarted. When DSM renews the certificate, restart TorrServer (the Helper's
**Restart** button) so the new copy is picked up. The choice is saved in
`torrserver.ssl.mode`, `torrserver.ssl.cert` and `torrserver.ssl.key`.

**Your own certificate on TorrServer's page.** Upload a PEM certificate chain and
an unencrypted key, or point TorrServer to files it can read. An upload is
copied to `ssl/uploaded.crt` and `ssl/uploaded.key`, and TorrServer saves the
choice in its own settings database, so it survives restarts and wins over
`server.pem` and `server.key`. For example, export the certificate in DSM
(**Control Panel → Security → Certificate → Action → Export certificate**) and
upload `fullchain.pem` and `privkey.pem` from the exported archive there.

**How the two fit together.** While a certificate uploaded on TorrServer's page
is in use, the Helper says so in its **SSL Certificate** card and does not let
you change the source there, because that choice would have no effect. Switch
TorrServer back to its self-signed certificate on its own page (the uploaded
copy is deleted then) and the Helper's choice is available again. A
certificate set on TorrServer's page by file path (not uploaded) is not
detected by the Helper.

**Back to self-signed in the Helper.** Choosing **TorrServer self-signed** after
a DSM certificate removes the copied `server.pem` and `server.key`, and
TorrServer makes its own pair when it is restarted. (Older versions kept the copied
certificate, so the DSM one was still served.)

**Older setups.** An installation that already used **Manual paths** keeps it and
it keeps working. New setups no longer offer it: use TorrServer's page.

**HTTPS without the permission.** DSM certificates need root, but you do not have
to give it. Let DSM provide HTTPS itself: **Control Panel → Login Portal →
Advanced → Reverse Proxy**, add a rule from an HTTPS address of your choice to
`http://localhost:<TorrServer port>`, and keep HTTPS in TorrServer switched
off. DSM then serves the certificate it already manages.

Problems with certificates are written to `TorrServer.log` (lines starting with
`certificate-helper:`; TorrServer's own messages about HTTPS are there as well).

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
  `TorrServer.log` (`helper-auth: ...`). Never expose port 42777.
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
| "Access denied" in the Helper | Sign in to DSM as an administrator. If you are one, see the reason: `sudo grep helper-auth /var/packages/TorrServer/var/TorrServer.log \| tail`. |
| "The TorrServer service user cannot write to this folder" | Give the **TorrServer** user Read/Write on the shared folder (see above). |
| "sudo: a password is required" or "DSM permissions are missing or out of date" | Only needed for the optional features: run `setup-permissions` again (see above). |
| TorrServer is not reachable | Check the Logs tab, then restart the package from DSM Package Center. |

Logs: everything goes to one file, `TorrServer.log`, in
`/var/packages/TorrServer/var/` and in the Helper's **Logs** tab. TorrServer,
the start/stop scripts (`service:`, `restart-torrserver:`), the Helper and the
certificate script (`certificate-helper:`) write to it in the same format. The
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
