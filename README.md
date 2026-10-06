# TorrServer DSM

Synology DSM package for [TorrServer](https://github.com/YouROK/TorrServer).

TorrServer DSM provides a native DSM interface for managing TorrServer on Synology NAS.

## Features

- DSM interface for package management

### Settings

- Port configuration for HTTP / HTTPS
- TorrServer cache configuration
- HTTPS
- Force HTTPS
- SSL certificate management
- HTTP authentication
- Logs and package status
- Restart TorrServer from DSM
- Optional one-time DSM root permission setup through Task Scheduler

## Requirements

- Synology DSM 7.3 or newer
- Supported architectures:
  - `amd64`
  - `arm64`
  - `arm7`

## Automatic update

    https://ggrigi.lt
Add to your Synology NAS Package Center sources!

## Building

Clone the repository:

    git clone https://github.com/vladlenas/TorrServer-DSM.git
    cd TorrServer-DSM

Build the SPK packages:

    make

The generated packages are placed in the `spk` directory.

To clean the build directory:

    make clean

### DSM permissions

Saving settings, restarting the package from the Helper and certificate
synchronization need a one-time sudo rule. Open **DSM Task Scheduler**, create a
**User-defined script** task, select **root** as the user, and run once:

    /var/packages/TorrServer/scripts/setup-permissions

Without it TorrServer itself runs normally, but the Helper is read-only. The
Helper shows the same instruction in a separate window and can check whether
the permission is configured.

The rule is not removed automatically on uninstall (package scripts do not run
as root). Remove it with:

    sudo rm -f /etc/sudoers.d/TorrServer

### Security notes

- The Helper listens on `127.0.0.1:42777` only and is reached through DSM nginx
  (`/webman/3rdparty/TorrServer/helper/`). It has no authentication of its own,
  so never expose that port.
- State-changing requests are accepted only from the same origin (CSRF guard).
- Directories and certificate paths must be under `/volumeN/` and must not
  contain `..` or point through symbolic links. The TorrServer directory must
  not contain spaces.

### Upgrading

Settings are kept across upgrades. On every upgrade the package removes
leftovers from older versions (obsolete files, `*.new` / `*.tmp` files and, for
the self-signed certificate mode, a stale `server.pem` / `server.key`). To
start from defaults, tick **Reset package settings to defaults** in the upgrade
wizard. Torrents and TorrServer's own database are not touched by the reset.

## TorrServer Version

The TorrServer version used by the package and the package version are defined
in `Makefile` (`TORRSERVER_VERSION`, `PKG_VERSION`). Bump `PKG_VERSION` to
trigger a CI build and a GitHub release. Downloaded binaries are cached per
TorrServer version in `dest_bin/`.

## Links

- [TorrServer Project](https://github.com/YouROK/TorrServer)
- [TorrServer DSM](https://github.com/vladlenas/TorrServer-DSM)
- [Support TorrServer Project](https://github.com/YouROK/TorrServer#donate)

## Credits

TorrServer by [YouROK](https://github.com/YouROK/TorrServer).

Synology SPK package maintained by [vladlenas](https://github.com/vladlenas).
