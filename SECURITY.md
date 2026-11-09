# EVIDEXA Security Policy

**Platform:** EVIDEXA — AI-Powered Digital Forensics & Document Intelligence  
**Repository:** [https://github.com/shubhamranswal/evidexa](https://github.com/shubhamranswal/evidexa)

---

## 1. Reporting Security Vulnerabilities

Security, evidentiary integrity, and memory safety are foundational to EVIDEXA. If you discover a security vulnerability, architectural boundary escape, or forensic tampering vector, please report it through private, responsible channels.

> [!IMPORTANT]
> **Please do not file public GitHub issues or discussions for undisclosed security vulnerabilities.**

### Supported Reporting Channel
Please report all security concerns confidentially via **[GitHub Security Advisories](https://github.com/shubhamranswal/evidexa/security/advisories/new)**.

When submitting a report, please include:
- A clear description of the vulnerability, potential impact, and affected components.
- Minimal reproduction steps, including sanitized proof-of-concept sample files where applicable.
- Environment details (operating system, Python version, installed dependencies).

### Response Expectations
EVIDEXA is currently under active pre-release development (`v0.1.0-alpha`) maintained as an independent open-source project. Submissions are reviewed on a best-effort basis, with triage prioritized for reproducible vulnerabilities that could cause process escape, unauthorized file system access, or evidence tampering.

---

## 2. Supported Versions

| Version | Status | Security Support |
|---|---|:---:|
| `v0.1.x` | Pre-Release (`alpha`) | Supported (Current active branch) |
| `< 0.1.0` | Development iterations | Unsupported |

---

## 3. Security Architecture & Boundary Invariants

EVIDEXA treats all incoming documents as untrusted inputs. Core security boundaries include:

1. **Non-Trusting File Ingestion:** Input documents undergo strict MIME and magic-byte signature validation before storage or analysis.
2. **Ephemeral Snapshot Isolation:** Analyzers operate solely on temporary analysis snapshots verified by pre/post SHA-256 checks, ensuring original evidentiary files remain unaltered.
3. **Subprocess Isolation:** Structural document parsers run within bounded child subprocesses governed by strict execution timeouts.
4. **Tenant & Case Isolation:** All forensic queries and storage references are strictly scoped to their owning case boundary.
5. **Zero Plaintext PII Persistence:** Sensitive financial account numbers and government identification strings are masked prior to database persistence.
6. **Append-Only Provenance Ledger:** Audit records are cryptographically hash-chained using SHA-256 digests.

For detailed technical explanations of architectural safeguards and defense-in-depth measures, refer to [Forensic Security & Evidence Integrity](docs/SECURITY.md).
