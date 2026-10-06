TORRSERVER_VERSION := MatriX.145.2
PKG_VERSION := 2.1.145.3

ARCHES := amd64 arm64 arm7

.PHONY: all clean

all: $(addprefix torrserver-,$(ARCHES))

torrserver-%:
	@./build-package.sh "$(TORRSERVER_VERSION)" "$*" "$(PKG_VERSION)"

clean:
	rm -rf spk dest_bin build
