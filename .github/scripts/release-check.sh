#!/bin/sh
# Checks that the repository is ready to be released, before you open the pull
# request that publishes it.
#
#   sh .github/scripts/release-check.sh
#
# Exit status 0 = ready (warnings are possible), 1 = do not release yet.
# RELEASE_CHECK_SKIP_TESTS=1 skips the test suites (they are slow).

cd "$(git rev-parse --show-toplevel)" || exit 1

problems=0
warnings=0

ok()   { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; problems=$((problems + 1)); }
warn() { printf 'warn  %s\n' "$1"; warnings=$((warnings + 1)); }

PKG_VERSION="$(sed -n 's/^PKG_VERSION *:= *//p' Makefile)"
TORRSERVER_VERSION="$(sed -n 's/^TORRSERVER_VERSION *:= *//p' Makefile)"
ARCHES="$(sed -n 's/^ARCHES *:= *//p' Makefile)"
TAG="v${PKG_VERSION}"
TORRSERVER_BUILD="${TORRSERVER_VERSION#*.}"            # MatriX.145.2 -> 145.2

echo "Release ${TAG} (TorrServer ${TORRSERVER_VERSION})"
echo

# ---- the working tree
if [ -z "$(git status --porcelain)" ]; then
    ok "working tree is clean"
else
    fail "uncommitted changes: commit or discard them first"
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" = "main" ]; then
    warn "you are on main; prepare the release on a branch and merge it by pull request"
else
    ok "on branch ${branch}"
fi

# ---- version
case "$PKG_VERSION" in
    *.${TORRSERVER_BUILD}) ok "PKG_VERSION ${PKG_VERSION} ends with the TorrServer build ${TORRSERVER_BUILD}" ;;
    *) fail "PKG_VERSION ${PKG_VERSION} must be <your version>.${TORRSERVER_BUILD} (the last numbers are TorrServer's build)" ;;
esac

remote_tags=""
if git remote get-url origin >/dev/null 2>&1; then
    if remote_tags="$(git ls-remote --tags origin 2>/dev/null)"; then
        remote_tags="$(printf '%s\n' "$remote_tags" | sed -n 's|.*refs/tags/\(v[^^]*\)$|\1|p')"
    else
        remote_tags=""
        warn "could not reach origin: tags on GitHub were not checked"
    fi
fi
all_tags="$(printf '%s\n%s\n' "$(git tag -l 'v*')" "$remote_tags" | sed '/^$/d' | sort -u)"

if printf '%s\n' "$all_tags" | grep -qx "$TAG"; then
    fail "tag ${TAG} already exists: raise PKG_VERSION"
else
    ok "tag ${TAG} is free"
fi

latest="$(printf '%s\n' "$all_tags" | sed 's/^v//' | sort -V | tail -1)"
if [ -z "$latest" ]; then
    ok "no earlier release to compare with"
elif [ "$(printf '%s\n%s\n' "$latest" "$PKG_VERSION" | sort -V | tail -1)" = "$PKG_VERSION" ] && [ "$latest" != "$PKG_VERSION" ]; then
    ok "${PKG_VERSION} is newer than the latest release ${latest}"
else
    fail "${PKG_VERSION} is not newer than the latest release ${latest}"
fi

# ---- release notes
top="$(grep -m1 '^## ' CHANGELOG.md | awk '{print $2}')"
if [ "$top" = "$PKG_VERSION" ]; then
    ok "CHANGELOG.md starts with an entry for ${PKG_VERSION}"
else
    fail "the top CHANGELOG.md entry is '${top}', expected '${PKG_VERSION}'"
fi
if sh .github/scripts/release-notes.sh "$PKG_VERSION" CHANGELOG.md >/dev/null 2>&1; then
    ok "the entry has text for the release notes"
else
    fail "the CHANGELOG.md entry for ${PKG_VERSION} is empty"
fi

# ---- pinned downloads
pins="$(grep -cE '^[0-9a-f]{64}  ' checksums.sha256 2>/dev/null)"
if [ "${pins:-0}" -eq 0 ]; then
    warn "checksums.sha256 has no pins: downloads are trusted on first use (rm -rf dest_bin && make checksums)"
else
    missing=""
    for arch in $ARCHES; do
        grep -q "  TorrServer-${TORRSERVER_VERSION}-linux-${arch}\$" checksums.sha256 || missing="${missing} TorrServer-${TORRSERVER_VERSION}-linux-${arch}"
    done
    for archive in $(grep -o 'ffprobe-[0-9.]*-linux-[a-z0-9-]*\.zip' build-package.sh | sort -u); do
        grep -q "  ${archive}\$" checksums.sha256 || missing="${missing} ${archive}"
    done
    if [ -z "$missing" ]; then
        ok "every download is pinned in checksums.sha256 (${pins} pins)"
    else
        fail "CI refuses unpinned downloads; missing:${missing}  (rm -rf dest_bin && make checksums)"
    fi
fi

# ---- tests
run_suite() { # run_suite <label> <command...>
    label="$1"; shift
    if output="$("$@" 2>&1)"; then
        ok "$label"
    else
        fail "$label"
        printf '%s\n' "$output" | tail -5 | sed 's/^/        /'
    fi
}
if [ "${RELEASE_CHECK_SKIP_TESTS:-0}" = "1" ]; then
    warn "test suites skipped"
else
    run_suite "python tests"        python3 -m unittest discover -s tests
    run_suite "package script tests" sh tests/test_scripts.sh
    if command -v node >/dev/null 2>&1; then
        run_suite "desktop app tests" node tests/test_ui.js
    else
        warn "node is not installed: desktop app tests were not run (CI runs them)"
    fi
    run_suite "build tests"         bash tests/test_build.sh
fi

echo
if [ "$problems" -gt 0 ]; then
    echo "NOT READY: ${problems} problem(s), ${warnings} warning(s)"
    exit 1
fi
echo "READY to release ${TAG} (${warnings} warning(s))"
echo
echo "Next:  git push -u origin ${branch}   ->  pull request  ->  wait for the green 'Tests'  ->  merge into main"
echo "CI then builds the packages and publishes the release ${TAG}."
exit 0
