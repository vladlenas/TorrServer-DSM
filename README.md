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

### Optional DSM permissions

TorrServer works without additional root privileges. If automatic certificate synchronization or restart from the Helper is required, open **DSM Task Scheduler**, create a **User-defined script** task, select **root** as the user, and run once:

    /var/packages/TorrServer/scripts/setup-permissions

The TorrServer Helper shows the same instruction in a separate window and can check whether the permission is configured.

## TorrServer Version

The TorrServer version used by the package is defined in `Makefile`:

    TORRSERVER_VERSION := MatriX.145.1

The package version is also defined in `Makefile`:

    PKG_VERSION := 1.4.145.1

## Links

- [TorrServer Project](https://github.com/YouROK/TorrServer)
- [TorrServer DSM](https://github.com/vladlenas/TorrServer-DSM)
- [Support TorrServer Project](https://github.com/YouROK/TorrServer#donate)

## Credits

TorrServer by [YouROK](https://github.com/YouROK/TorrServer).

Synology SPK package maintained by [vladlenas](https://github.com/vladlenas).
