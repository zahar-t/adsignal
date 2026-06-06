"""
Java 17+ discovery for PySpark 4.x.

PySpark launches its JVM from ``JAVA_HOME`` (or ``java`` on ``PATH``). On dev
machines the default ``java`` is often an older JRE while a suitable JDK is
installed elsewhere (e.g. a keg-only Homebrew ``openjdk@17`` that
``/usr/libexec/java_home`` cannot see). Rather than force every user to export
``JAVA_HOME`` by hand, :func:`ensure_java` locates a 17+ JDK and points the
process at it before Spark starts.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess

MIN_JAVA_MAJOR = 17


def java_major(java_bin: str) -> int | None:
    """Return the major version reported by ``java_bin -version``, or None."""
    try:
        result = subprocess.run([java_bin, "-version"], capture_output=True, text=True)
    except (OSError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r'version "(\d+)(?:\.(\d+))?', result.stderr or result.stdout)
    if not match:
        return None
    major = int(match.group(1))
    # Legacy "1.8" scheme → 8.
    if major == 1 and match.group(2):
        return int(match.group(2))
    return major


def _home_ok(home: str, min_major: int) -> bool:
    return bool(home) and (java_major(os.path.join(home, "bin", "java")) or 0) >= min_major


def find_java_home(min_major: int = MIN_JAVA_MAJOR) -> str | None:
    """Find a JAVA_HOME with Java >= ``min_major``, searching common locations."""
    candidates: list[str] = []

    # 1. Current JAVA_HOME.
    if os.environ.get("JAVA_HOME"):
        candidates.append(os.environ["JAVA_HOME"])

    # 2. Home derived from `java` on PATH.
    java_path = shutil.which("java")
    if java_path:
        candidates.append(os.path.dirname(os.path.dirname(os.path.realpath(java_path))))

    # 3. macOS java_home selector.
    try:
        sel = subprocess.run(
            ["/usr/libexec/java_home", "-v", str(min_major)], capture_output=True, text=True
        )
        if sel.returncode == 0 and sel.stdout.strip():
            candidates.append(sel.stdout.strip())
    except (OSError, FileNotFoundError):
        pass

    # 4. Homebrew keg-only locations (Apple Silicon + Intel).
    for base in ("/opt/homebrew/opt", "/usr/local/opt"):
        candidates.append(
            os.path.join(base, f"openjdk@{min_major}", "libexec", "openjdk.jdk", "Contents", "Home")
        )

    # 5. Installed JVMs (macOS) / common Linux locations.
    candidates.extend(glob.glob("/Library/Java/JavaVirtualMachines/*/Contents/Home"))
    candidates.extend(glob.glob(f"/usr/lib/jvm/*{min_major}*"))

    for home in candidates:
        if _home_ok(home, min_major):
            return home
    return None


def ensure_java(min_major: int = MIN_JAVA_MAJOR) -> str | None:
    """Point this process at a Java >= ``min_major`` JDK (sets JAVA_HOME + PATH).

    Returns the JAVA_HOME used, or None if no suitable JDK was found.
    """
    home = find_java_home(min_major)
    if home:
        os.environ["JAVA_HOME"] = home
        bin_dir = os.path.join(home, "bin")
        if bin_dir not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    return home
