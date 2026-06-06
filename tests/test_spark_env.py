"""Tests for Java discovery and the Lakekeeper/MinIO DNS shim."""
import socket
import sys

import pytest

from adsignal import lakehouse_dns
from adsignal.spark import java

# ── Java discovery ────────────────────────────────────────────────────────────


def test_java_major_on_non_java_binary_returns_none():
    assert java.java_major(sys.executable) is None


def test_find_java_home_returns_valid_jdk_or_none():
    home = java.find_java_home(17)
    if home is not None:
        assert (java.java_major(f"{home}/bin/java") or 0) >= 17


def test_ensure_java_sets_env_when_found(monkeypatch):
    monkeypatch.delenv("JAVA_HOME", raising=False)
    home = java.ensure_java(17)
    if home is not None:
        import os

        assert os.environ["JAVA_HOME"] == home
        assert f"{home}/bin" in os.environ["PATH"]


# ── DNS shim ──────────────────────────────────────────────────────────────────

BOGUS_HOST = "adsignal-nonexistent-internal-host-xyz"


def test_needs_shim_false_when_disabled(monkeypatch):
    monkeypatch.setattr(lakehouse_dns.settings, "iceberg_s3_internal_host", "")
    assert lakehouse_dns.needs_shim() is False


def test_needs_shim_true_for_unresolvable_host(monkeypatch):
    monkeypatch.setattr(lakehouse_dns.settings, "iceberg_s3_internal_host", BOGUS_HOST)
    assert lakehouse_dns.needs_shim() is True


def test_target_ip_for_localhost_endpoint(monkeypatch):
    monkeypatch.setattr(
        lakehouse_dns.settings, "iceberg_s3_endpoint", "http://localhost:9000"
    )
    assert lakehouse_dns._target_ip() == "127.0.0.1"


def test_jvm_hosts_file_maps_internal_and_loopback(monkeypatch):
    monkeypatch.setattr(lakehouse_dns.settings, "iceberg_s3_internal_host", BOGUS_HOST)
    monkeypatch.setattr(
        lakehouse_dns.settings, "iceberg_s3_endpoint", "http://localhost:9000"
    )
    path = lakehouse_dns.jvm_hosts_file()
    assert path is not None
    with open(path) as fh:
        content = fh.read()
    assert f"127.0.0.1 {BOGUS_HOST}" in content
    assert "127.0.0.1 localhost" in content
    # Machine hostname must be present (JVM hosts file replaces all resolution).
    assert socket.gethostname() in content


def test_jvm_hosts_file_none_when_disabled(monkeypatch):
    monkeypatch.setattr(lakehouse_dns.settings, "iceberg_s3_internal_host", "")
    assert lakehouse_dns.jvm_hosts_file() is None


def test_patch_python_dns_rewrites_only_internal_host(monkeypatch):
    monkeypatch.setattr(lakehouse_dns.settings, "iceberg_s3_internal_host", BOGUS_HOST)
    monkeypatch.setattr(
        lakehouse_dns.settings, "iceberg_s3_endpoint", "http://localhost:9000"
    )
    # Reset the module-level patch latch and restore the real resolver afterward.
    original = socket.getaddrinfo
    monkeypatch.setattr(lakehouse_dns, "_python_patched", False)
    try:
        assert lakehouse_dns.patch_python_dns() is True
        # The bogus host now resolves (to loopback) instead of raising.
        infos = socket.getaddrinfo(BOGUS_HOST, 9000)
        assert any(info[4][0] == "127.0.0.1" for info in infos)
        # Unrelated names still resolve normally.
        assert socket.getaddrinfo("localhost", 80)
    finally:
        socket.getaddrinfo = original


@pytest.mark.skip(reason="documents that an already-resolvable host needs no shim")
def test_needs_shim_false_when_host_resolves():
    pass
