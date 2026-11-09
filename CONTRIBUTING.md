# Contributing to EVIDEXA

Thank you for your interest in contributing to **EVIDEXA** — AI-Powered Digital Forensics & Document Intelligence.

EVIDEXA is built with enterprise rigor, mathematical precision, and forensic defensibility. We welcome contributions that maintain these standards.

---

## 1. Guiding Engineering Principles

All contributions must adhere to our core architectural and product principles:

1. **Evidence Before Conclusions:** Implement deterministic detection and observable facts before probabilistic interpretations.
2. **Strict Layer Isolation:** Domain models and business logic must remain pure Python, free of database, framework, or presentation dependencies.
3. **Traceability:** Every finding or extracted field must maintain traceable links to document IDs, page indices, normalized coordinates (`NORMALIZED_0_1`), or token IDs.
4. **Subprocess Isolation:** Forensic parsing engines that handle untrusted byte streams must execute in supervisor-bounded subprocesses.
5. **Exact Financial Precision:** Use `Decimal` with formal minor unit quantization for monetary values; floating-point currency representation is prohibited.
6. **Zero Plaintext PII:** Ensure sensitive identifiers (PANs, Aadhaar, account numbers) are masked before persistence.

---

## 2. Development Setup

### Prerequisites
- **Python:** 3.12 (64-bit)
- Standard development tools (`git`, virtual environment managers)

### Setup Steps

```powershell
# 1. Clone repository
git clone https://github.com/shubhamranswal/evidexa.git
cd evidexa

# 2. Create and activate a Python 3.12 virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows PowerShell
# source .venv/bin/activate  # Linux / macOS

# 3. Install package in editable mode with development dependencies
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# 4. Optional: Configure environment settings
# copy .env.example .env    # Windows
# cp .env.example .env      # Linux / macOS

# 5. Apply database migrations
alembic upgrade head
```

> [!NOTE]
> All optical recognition models are bundled automatically via `rapidocr-onnxruntime`; no external model downloads or GPU setup are needed.

---

## 3. Mandatory Quality & Verification Gates

Before submitting code, all four verification gates must pass cleanly:

### 1. Test Suite (100% Pass Rate)
```powershell
python -m pytest
```
All unit, integration, and architecture boundary tests must pass. New features require corresponding automated tests.

### 2. Linting (Ruff)
```powershell
python -m ruff check src tests
```
Zero linting warnings or errors across all source and test files.

### 3. Formatting (Ruff)
```powershell
python -m ruff format --check src tests
```
Standardized formatting with 100-character line length limit. Auto-format with `python -m ruff format src tests`.

### 4. Static Type Checking (MyPy Strict Mode)
```powershell
python -m mypy src
```
Strict typing with zero type warnings and `disallow_untyped_defs = true`.

---

## 4. Architectural Boundaries

The platform enforces Clean Architecture boundaries:

- **`src/document_intelligence/domain/`**: Pure domain entities, value objects, and enums. Zero external library imports.
- **`src/document_intelligence/modules/`**: Modular application services, interfaces, schemas, and forensic adapters.
- **`src/document_intelligence/infrastructure/`**: Database persistence, SQLAlchemy models, and storage implementations.
- **`src/document_intelligence/api/`**: FastAPI routers, request/response models, and dependency injection.

---

## 5. Submitting Pull Requests

1. Fork the repository and create a feature branch (`feature/your-feature-name` or `fix/your-fix-name`).
2. Implement your changes adhering to code style and architecture boundaries.
3. Run the full verification suite (pytest, ruff check, ruff format, mypy).
4. Provide a clear PR description detailing:
   - The problem addressed and forensic justification.
   - Files changed and tests added.
   - Verification output confirming passing gates.

