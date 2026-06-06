"""
Local-dev DNS shim for the Lakekeeper + MinIO lakehouse.

The Lakekeeper REST catalog runs inside Docker and reaches MinIO at its
docker-internal hostname (the compose service name, ``minio``). With S3 remote
signing enabled, Lakekeeper *vends that same hostname* to clients — so a host
process (Spark driver, the dashboard, the API, the pandas ETL) is told to PUT/GET
objects at ``http://minio:9000/...``. The host can't resolve ``minio``, so every
read/write fails with a DNS error even though MinIO is published on
``localhost:9000``.

There is no single endpoint value that works for both Lakekeeper-in-Docker and
host clients, so rather than mutate shared infra (the warehouse storage profile)
or require a root ``/etc/hosts`` edit, this module bridges the gap *per process*:

* :func:`patch_python_dns` — rewrites ``socket.getaddrinfo`` so Python clients
  (pyiceberg / s3fs / aiobotocore) resolve the internal host to the published IP.
* :func:`jvm_hosts_file` — writes a ``jdk.net.hosts.file`` so the Spark JVM
  resolves the internal host (plus loopback + the local machine name, which the
  JVM hosts file must also cover since it replaces system resolution).

Both are no-ops when the internal host already resolves (e.g. the user added an
``/etc/hosts`` entry) or when ``settings.iceberg_s3_internal_host`` is empty.
"""
from __future__ import annotations

import os
import socket
import tempfile
from urllib.parse import urlparse

from adsignal.config import settings

_python_patched = False


def _internal_host() -> str:
    return (settings.iceberg_s3_internal_host or "").strip()


def _target_ip() -> str:
    """The IP host clients should actually hit (derived from the S3 endpoint)."""
    host = urlparse(settings.iceberg_s3_endpoint).hostname or "localhost"
    try:
        return socket.gethostbyname(host)
    except OSError:
        return "127.0.0.1"


def needs_shim() -> bool:
    """True when the internal host is set but doesn't already resolve on this host."""
    host = _internal_host()
    if not host:
        return False
    try:
        socket.getaddrinfo(host, None)
        return False
    except OSError:
        return True


def patch_python_dns() -> bool:
    """Map the internal MinIO host → published IP for Python socket resolution.

    Idempotent and surgical: only lookups for the exact internal host are
    rewritten; everything else passes through unchanged. Returns True if a patch
    is now in effect.
    """
    global _python_patched
    if _python_patched:
        return True
    if not needs_shim():
        return False

    host = _internal_host()
    ip = _target_ip()
    original = socket.getaddrinfo

    def patched(hostname, *args, **kwargs):
        if hostname == host:
            hostname = ip
        return original(hostname, *args, **kwargs)

    socket.getaddrinfo = patched  # type: ignore[assignment]
    _python_patched = True
    return True


def jvm_hosts_file() -> str | None:
    """Write a JDK hosts file mapping the internal host (+ loopback/machine name).

    Returns the file path for use as ``-Djdk.net.hosts.file=...``, or None when no
    shim is needed. The JVM hosts file replaces *all* system resolution for the
    JVM, so it must also include ``localhost`` and the local machine hostname that
    Spark resolves at startup.
    """
    if not needs_shim():
        return None

    host = _internal_host()
    ip = _target_ip()
    machine = socket.gethostname()
    short = machine.split(".")[0]

    lines = [f"{ip} localhost", "::1 localhost", f"{ip} {host}"]
    for name in (machine, short):
        if name and name != "localhost":
            lines.append(f"{ip} {name}")

    path = os.path.join(tempfile.gettempdir(), "adsignal_jvm_hosts")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return path
