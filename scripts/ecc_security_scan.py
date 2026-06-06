#!/usr/bin/env python3
"""
ECC security gate — scan the repo for dangerous invisible Unicode.

A Python port of ECC's ``scripts/ci/check-unicode-safety.js`` (MIT,
https://github.com/affaan-m/ecc). Detects invisible/format code points used for
"ASCII smuggling" prompt injection and Trojan-Source attacks. Exits non-zero on
any violation so it can act as a CI gate (see ``make security`` and ci.yml).

Usage:
    python scripts/ecc_security_scan.py [ROOT]   # defaults to repo root
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adsignal.security import scan_path


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent.parent)
    violations = scan_path(root)

    if violations:
        print("ECC unicode safety: violations detected", file=sys.stderr)
        for v in violations:
            print(f"  {v.file}:{v.line}:{v.column}  dangerous-invisible {v.code_point}", file=sys.stderr)
        print(f"\n{len(violations)} violation(s). See ECC_USAGE.md.", file=sys.stderr)
        return 1

    print("ECC unicode safety check passed — no dangerous invisible Unicode found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
