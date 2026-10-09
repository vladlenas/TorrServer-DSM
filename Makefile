TORRSERVER_VERSION := MatriX.146
PKG_VERSION := 2.7.146

ARCHES := amd64 arm64 arm7

.PHONY: all clean checksums

all: $(addprefix torrserver-,$(ARCHES))

torrserver-%:
	@./build-package.sh "$(TORRSERVER_VERSION)" "$*" "$(PKG_VERSION)"

# Pin SHA-256 sums of the downloads in checksums.sha256 (trust on first use:
# review the file, compare with the upstream release pages, then commit it).
# Delete dest_bin first to pin binaries that are already cached.
checksums:
	@for arch in $(ARCHES); do \
		UPDATE_CHECKSUMS=1 DOWNLOAD_ONLY=1 ./build-package.sh "$(TORRSERVER_VERSION)" "$$arch" "$(PKG_VERSION)" || exit 1; \
	done

clean:
	rm -rf spk dest_bin build
