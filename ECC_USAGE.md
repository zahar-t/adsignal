# ECC Integration — AdSignal

This document explains how the [ECC operator system](https://github.com/affaan-m/ecc)
(MIT) is integrated into AdSignal, what it protects, and how to use and extend it.

## What ECC is

ECC ("Every Commit Counts") is a harness-native operator system for agentic
development: skills, hooks, rules, agents, MCP configs, and — most relevant here —
a **security layer** that hardens AI-assisted workflows against prompt injection,
"ASCII smuggling," and supply-chain attacks. ECC's security guide frames the core
risk as Simon Willison's *lethal trifecta*: private data + untrusted content +
external communication sharing one runtime.

## Why it fits AdSignal

AdSignal is a textbook lethal-trifecta system:

1. **Untrusted content** — it ingests ad creative copy from the Meta Ad Library
   (and synthetic/scraped fallbacks).
2. **Private data** — brand spend signals, credentials, an LLM provider.
3. **External communication** — that ad text is forwarded into an LLM narrative
   engine (Ollama / LM Studio / Anthropic / OpenAI).

So an attacker could embed hidden instructions inside ad copy using invisible
Unicode (zero-width characters, bidi overrides, or the Unicode **Tag block** —
the canonical "ASCII smuggling" vector). A human reviewing the ad sees normal
text; the LLM ingests the hidden bytes as instructions.

## What was integrated

ECC's `scripts/ci/check-unicode-safety.js` was ported to Python and wired into
AdSignal in two complementary places:

### 1. Runtime defense — `adsignal/security.py`

`sanitize_external_text(text)` strips dangerous invisible code points from any
externally-sourced string while leaving every visible character intact. It is
applied at the two chokepoints where untrusted text enters or approaches the LLM:

| Location | What it protects |
|---|---|
| `adsignal/ingest/meta_client.py` (`_normalise_meta_ad`) | Ad copy is sanitized **at ingest**, before it is persisted to MongoDB. |
| `adsignal/llm/prompts.py` (`build_brief_prompt`) | Defense in depth — creative themes are re-sanitized before the prompt is assembled for the model. |

The dangerous code-point set (`is_dangerous_invisible`) is a faithful port of
ECC's detector: zero-width spaces/joiners, the BOM, bidi overrides/isolates
(Trojan Source, CVE-2021-42574), variation selectors, the Unicode Tag block,
Mongolian/Hangul fillers, and invisible math operators.

### 2. CI gate — `scripts/ecc_security_scan.py`

Scans the whole repository for dangerous invisible Unicode and **exits non-zero**
on any hit, mirroring ECC's `check-unicode-safety.js`. It is wired into:

- `make security` — run the scan on demand.
- `make verify` and `make ci-local` — part of the local quality gate.
- `.github/workflows/ci.yml` — a "Security gate" step that runs before tests.

## How to use it

```bash
# Scan the repo for invisible-Unicode smuggling (CI gate)
make security
# or directly:
python scripts/ecc_security_scan.py [PATH]

# Sanitize untrusted text in code:
from adsignal.security import sanitize_external_text
clean = sanitize_external_text(untrusted_ad_copy)
```

If the scan fails, it prints `file:line:column  dangerous-invisible U+XXXX` for
each violation. Legitimate test fixtures that need such characters should build
them with `chr(0x...)` (see `tests/test_security.py`) so the source file itself
stays clean.

Tests covering this integration live in `tests/test_security.py`.

## Extending with the full ECC toolkit

This integration intentionally adopts one high-value, language-agnostic ECC
capability rather than vendoring the whole framework. To go further:

- Install ECC as a Claude Code plugin (`.claude-plugin/` in the ECC repo) to get
  its `/tdd`, `/python-review`, `/verify`, and `/code-review` slash commands plus
  agentic-security hooks during development.
- Adopt ECC's other CI validators (`scan-supply-chain-iocs.js`,
  `validate-no-personal-paths.js`) if/when a Node toolchain is added to CI.

Attribution: detection logic ported from ECC (https://github.com/affaan-m/ecc),
MIT License.
