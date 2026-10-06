#!/bin/sh
# Tests for the package shell scripts. No DSM needed.
# Run:  sh tests/test_scripts.sh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="${ROOT}/src/scripts"
FAILED=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass() { printf 'PASS %s\n' "$1"; }
fail() { printf 'FAIL %s\n' "$1"; FAILED=$((FAILED + 1)); }
check() { # check <description> <command...>
    desc="$1"; shift
    if "$@"; then pass "$desc"; else fail "$desc"; fi
}
has()  { [ -e "$VAR/$1" ]; }
hasnt(){ [ ! -e "$VAR/$1" ]; }

setup_var() { # setup_var <ssl mode>
    rm -rf "$TMP/var" "$TMP/target"
    VAR="$TMP/var"; mkdir -p "$VAR" "$TMP/target/ui"
    for f in torrserver.fuse.path server.pem server.key a.new b.tmp c.stage TorrServer.pid accs.db; do echo x > "$VAR/$f"; done
    echo 9999 > "$VAR/torrserver.port"
    echo "$1" > "$VAR/torrserver.ssl.mode"
}

run_setup() { # run_setup <shell snippet>   (extra env passed through)
    env SYNOPKG_PKGNAME=TorrServer SYNOPKG_DSM_VERSION_MAJOR=7 \
        SYNOPKG_PKGVAR="$VAR" SYNOPKG_PKGDEST="$TMP/target" \
        sh -c ". '${SCRIPTS}/service-setup'; $1"
}

echo "== service-setup: upgrade migration"
setup_var self
run_setup migrate_config >/dev/null
check "settings kept"                       has torrserver.port
check "port still 9999"                     [ "$(cat "$VAR/torrserver.port")" = 9999 ]
check "accounts kept"                       has accs.db
check "obsolete torrserver.fuse.path gone"  hasnt torrserver.fuse.path
check "leftover *.new/*.tmp/*.stage gone"   sh -c "[ ! -e '$VAR/a.new' ] && [ ! -e '$VAR/b.tmp' ] && [ ! -e '$VAR/c.stage' ]"
check "stale server.pem/key gone (self)"    sh -c "[ ! -e '$VAR/server.pem' ] && [ ! -e '$VAR/server.key' ]"
check "stale pid file gone"                 hasnt TorrServer.pid
check "schema recorded"                     [ "$(cat "$VAR/config.schema")" = 2 ]

setup_var dsm
run_setup migrate_config >/dev/null
check "server.pem kept in dsm mode"         has server.pem

echo "== second upgrade is a no-op for certificates"
run_setup migrate_config >/dev/null
check "server.pem still kept"               has server.pem

echo "== upgrade wizard: reset requested"
setup_var dsm
echo 1 > "$VAR/cache.pending"
run_setup "wizard_reset_settings=true; migrate_config" >/dev/null
check "port setting removed"                hasnt torrserver.port
check "accounts removed"                    hasnt accs.db
check "pending cache removed"               hasnt cache.pending
check "certificates removed"                sh -c "[ ! -e '$VAR/server.pem' ]"
check "schema recorded after reset"         has config.schema

echo "== service-setup: sourcing has no side effects (status polls)"
setup_var self; rm -f "$VAR/config.schema"
run_setup ":" >/dev/null 2>&1
check "no .sc written when merely sourced"  sh -c "[ -z \"\$(ls '$TMP/target/ui')\" ]"
check "no schema written when sourced"      hasnt config.schema

echo "== service-setup: command line"
setup_var self; echo 1 > "$VAR/torrserver.auth"; echo '{"u":"p"}' > "$VAR/accs.db"
out="$(run_setup 'echo "$SERVICE_COMMAND"')"
check "auth flag passed"                    sh -c "echo '$out' | grep -q ' -a '"
check "service log != torrserver log"       run_setup '[ "$LOG_FILE" != "$TORRSERVER_LOG" ]'

echo "== service-setup: FUSE path with spaces is skipped"
setup_var self; mkdir -p "$TMP/My Data/FUSE"; echo 1 > "$VAR/torrserver.fuse"; echo "$TMP/My Data" > "$VAR/torrserver.dir"
check "no --fusepath"                       run_setup '[ -z "$FUSE_ARGS" ] && [ -n "$FUSE_SKIPPED_REASON" ]'
setup_var self; mkdir -p "$TMP/Data/FUSE"; echo 1 > "$VAR/torrserver.fuse"; echo "$TMP/Data" > "$VAR/torrserver.dir"
check "normal path gets --fusepath"         run_setup 'case "$FUSE_ARGS" in "--fusepath "*"/Data/FUSE") true;; *) false;; esac'

echo "== service-setup: firewall file"
setup_var self; echo 1 > "$VAR/torrserver.https"; echo 9443 > "$VAR/torrserver.https.port"
run_setup update_firewall_port >/dev/null 2>&1
check "web + https ports listed"            grep -q 'dst.ports="9999,9443/tcp"' "$TMP/target/ui/TorrServer.sc"
check "helper port NOT exposed"             sh -c "! grep -q 42777 '$TMP/target/ui/TorrServer.sc'"

echo "== certificate-helper: path resolution"
mkdir -p "$TMP/syno/sub" "$TMP/volume1/share"
echo c > "$TMP/syno/sub/cert.pem"; echo c > "$TMP/volume1/share/ok.pem"
ln -s /etc/passwd "$TMP/syno/sub/evil.pem"; ln -s "$TMP/syno/sub/cert.pem" "$TMP/volume1/share/link.pem"
sed -n '/^resolve_path()/,/^}/p' "${SCRIPTS}/certificate-helper" \
  | sed "s|\${CERT_ROOT}|$TMP/syno|g; s|/volume\[0-9\]\*/\*|$TMP/volume[0-9]*/*|" > "$TMP/fn.sh"
allowed() { sh -c ". '$TMP/fn.sh'; resolve_path '$2' $1" >/dev/null 2>&1; }
check "dsm: normal file allowed"            allowed dsm "$TMP/syno/sub/cert.pem"
check "dsm: '..' rejected"                  sh -c "! sh -c \". '$TMP/fn.sh'; resolve_path '$TMP/syno/../../../etc/passwd' dsm\" >/dev/null 2>&1"
check "dsm: symlink out of root rejected"   sh -c "! sh -c \". '$TMP/fn.sh'; resolve_path '$TMP/syno/sub/evil.pem' dsm\" >/dev/null 2>&1"
check "manual: normal file allowed"         allowed manual "$TMP/volume1/share/ok.pem"
check "manual: symlink out of share rejected" sh -c "! sh -c \". '$TMP/fn.sh'; resolve_path '$TMP/volume1/share/link.pem' manual\" >/dev/null 2>&1"

echo "== prepare-directory: rejects bad input (needs root; rejections change nothing)"
if [ "$(id -u)" -eq 0 ]; then RUN=""; elif sudo -n true 2>/dev/null; then RUN="sudo -n"; else RUN="skip"; fi
if [ "$RUN" = skip ]; then
    echo "SKIP (not root and no passwordless sudo)"
else
    for bad in "/volume1/../etc/x" "/volume1" "/etc" "/volume1/a b" "/volume1/ok/.."; do
        check "rejects '$bad'"              sh -c "! $RUN sh '${SCRIPTS}/prepare-directory' '$bad' >/dev/null 2>&1"
    done
fi

echo
if [ "$FAILED" -eq 0 ]; then echo "ALL PASSED"; else echo "FAILED: $FAILED"; exit 1; fi
