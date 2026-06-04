#!/usr/bin/env bash
# check_java.sh — verify Java 17+ is available for PySpark 4.x
set -e

REQUIRED_VERSION=17

if ! command -v java &>/dev/null; then
    echo ""
    echo "ERROR: Java not found. PySpark 4.x requires Java 17+."
    echo ""
    echo "  macOS:   brew install openjdk@17"
    echo "           export JAVA_HOME=\$(/usr/libexec/java_home -v 17)"
    echo ""
    echo "  Ubuntu:  sudo apt install openjdk-17-jdk"
    echo "           export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64"
    echo ""
    echo "  Windows: winget install Microsoft.OpenJDK.17"
    echo "           Then set JAVA_HOME in System Environment Variables"
    echo ""
    exit 1
fi

JAVA_VER=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}' | cut -d'.' -f1)

# Handle old-style version strings like "1.8"
if [ "$JAVA_VER" = "1" ]; then
    JAVA_VER=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}' | cut -d'.' -f2)
fi

if [ "$JAVA_VER" -lt "$REQUIRED_VERSION" ] 2>/dev/null; then
    echo ""
    echo "ERROR: Java $JAVA_VER found, but Java $REQUIRED_VERSION+ is required for PySpark 4.x."
    echo ""
    echo "  macOS:   brew install openjdk@17 && export JAVA_HOME=\$(/usr/libexec/java_home -v 17)"
    echo "  Ubuntu:  sudo apt install openjdk-17-jdk"
    echo "  Windows: winget install Microsoft.OpenJDK.17"
    echo ""
    exit 1
fi

echo "✓ Java $JAVA_VER found (Java $REQUIRED_VERSION+ required — OK)"
exit 0
