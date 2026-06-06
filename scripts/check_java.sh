#!/usr/bin/env bash
# check_java.sh — verify a Java 17+ JDK is available for PySpark 4.x.
#
# Searches the same locations as adsignal/spark/java.py (PATH, JAVA_HOME,
# /usr/libexec/java_home, Homebrew keg-only openjdk@17, installed JVMs) so a
# keg-only JDK that isn't on PATH still counts. On success it prints the JAVA_HOME
# to export; it does NOT fail the build when a usable JDK exists somewhere.
set -e

REQUIRED_VERSION=17

major_of() {
    # Echo the major version of the java binary in $1/bin/java, or nothing.
    local jbin="$1/bin/java"
    [ -x "$jbin" ] || return 0
    local ver
    ver=$("$jbin" -version 2>&1 | awk -F '"' '/version/ {print $2}' | head -1)
    if [[ "$ver" == 1.* ]]; then
        echo "$ver" | cut -d'.' -f2
    else
        echo "$ver" | cut -d'.' -f1
    fi
}

candidates=()
[ -n "$JAVA_HOME" ] && candidates+=("$JAVA_HOME")
if command -v java &>/dev/null; then
    jp="$(command -v java)"
    candidates+=("$(cd "$(dirname "$(readlink "$jp" || echo "$jp")")/.." 2>/dev/null && pwd)")
fi
if [ -x /usr/libexec/java_home ]; then
    jh="$(/usr/libexec/java_home -v "$REQUIRED_VERSION" 2>/dev/null || true)"
    [ -n "$jh" ] && candidates+=("$jh")
fi
candidates+=("/opt/homebrew/opt/openjdk@${REQUIRED_VERSION}/libexec/openjdk.jdk/Contents/Home")
candidates+=("/usr/local/opt/openjdk@${REQUIRED_VERSION}/libexec/openjdk.jdk/Contents/Home")
for d in /Library/Java/JavaVirtualMachines/*/Contents/Home /usr/lib/jvm/*"${REQUIRED_VERSION}"*; do
    [ -d "$d" ] && candidates+=("$d")
done

for home in "${candidates[@]}"; do
    [ -d "$home" ] || continue
    v="$(major_of "$home")"
    if [ -n "$v" ] && [ "$v" -ge "$REQUIRED_VERSION" ] 2>/dev/null; then
        echo "✓ Java $v found at: $home"
        echo "  (export JAVA_HOME=\"$home\" — the ETL scripts also auto-detect this)"
        exit 0
    fi
done

echo ""
echo "ERROR: No Java $REQUIRED_VERSION+ JDK found. PySpark 4.x requires Java $REQUIRED_VERSION+."
echo ""
echo "  macOS:   brew install openjdk@17"
echo "  Ubuntu:  sudo apt install openjdk-17-jdk"
echo "  Windows: winget install Microsoft.OpenJDK.17"
echo ""
echo "  Or run the Spark-free engine: python scripts/run_etl.py --engine pandas"
echo ""
exit 1
