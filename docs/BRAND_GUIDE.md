# EVIDEXA Brand Identity & Design Guide

**Intelligence Behind Every Evidence.**  
*Uncover the Truth. Verify Every Detail.*

---

## 1. Brand Essence & Positioning

**EVIDEXA** is an enterprise-grade AI-powered digital forensics and document intelligence platform. It bridges the critical divide between raw forensic file analysis, computer vision, optical character recognition, and cross-document relational intelligence.

EVIDEXA is designed for serious investigative environments: fraud examinations, corporate underwriting, forensic accounting, compliance audits, and legal discovery.

### Official Brand Core
- **Brand Name:** EVIDEXA (all capitals preferred in typography and branding; "Evidexa" acceptable in standard running prose).
- **Category:** AI-Powered Digital Forensics & Document Intelligence.
- **Short Description:** Intelligent document forensics and evidence analysis, powered by AI.
- **Short Tagline:** *Intelligence Behind Every Evidence.*
- **Main Tagline:** *Uncover the Truth. Verify Every Detail.*
- **Public Repository:** [https://github.com/shubhamranswal/evidexa](https://github.com/shubhamranswal/evidexa)

---

## 2. Core Philosophy & Guiding Principles

Every communication, user interface element, API response, and technical report bearing the EVIDEXA name must adhere to seven inviolable principles:

1. **Evidence before conclusions:** The system establishes verified, observable facts before proposing interpretations.
2. **Traceability for every finding:** Every forensic finding, extracted value, and detected relationship must link to verifiable bounding boxes, byte ranges, or token IDs.
3. **Explainable analysis over opaque AI judgments:** Black-box verdict scores without evidentiary breakdown are strictly rejected.
4. **Human investigators retain decision authority:** EVIDEXA empowers and accelerates human investigators; it is never marketed or deployed as an autonomous fraud judge.
5. **An anomaly is not automatically proof of fraud:** Formatting errors, benign scanning artifacts, and OCR ambiguities must be presented objectively as anomalies requiring review, not convicted as fraud.
6. **Original documents and evidence provenance must be protected:** Ingestion snapshots, cryptographic hash verification, and immutable audit logs guarantee forensic chain of custody.
7. **Deterministic forensic processing remains authoritative:** Mathematical algorithms, structural parsers, and explicit rule engines establish ground truth; AI models assist in contextual interpretation and synthesis.

---

## 3. Visual Identity

The visual identity of EVIDEXA communicates precision, security, scientific rigor, and understated authority.

### 3.1 Color Palette

```
Foundation Palette:
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│ Deep Midnight (Base)    │  │ Dark Charcoal (Surface) │  │ Border Slate (Dividers) │
│ HEX: #0B132B            │  │ HEX: #1C2541            │  │ HEX: #2E3856            │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘

Accent & Signal Palette:
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│ Electric Cyan (Focus)   │  │ Aqua Glow (Highlights)  │  │ Deep Blue (Secondary)   │
│ HEX: #00E5FF            │  │ HEX: #48CAE4            │  │ HEX: #0077B6            │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘

Evidentiary Status Palette:
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│ Confirmed (Emerald)     │  │ Candidate (Amber)       │  │ Contradicted (Crimson)  │
│ HEX: #10B981            │  │ HEX: #F59E0B            │  │ HEX: #EF4444            │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
```

- **Deep Midnight (`#0B132B`):** Primary background foundation for dark-mode UI and documentation headers. Represents depth and operational security.
- **Dark Charcoal (`#1C2541`):** Primary card, sidebar, and container background.
- **Electric Cyan (`#00E5FF`):** Controlled accent color for active interactive states, graph edges, and focal indicators. Used sparingly to draw eye focus to verified evidence.
- **Aqua Glow (`#48CAE4`):** Secondary accent for hover states, bounding box highlights, and text links.
- **Deep Blue (`#0077B6`):** Solid brand accent for primary buttons and container borders.

### 3.2 Geometric Mark & Icon Concept

The official icon concept for EVIDEXA consists of a **Layered Geometric Hexagon with an Intersecting Inspection Prism and Node Network**:
- The hexagonal silhouette symbolizes structural stability and cryptographic integrity.
- Three internal layered planes represent the forensic pipeline: Document Layer (raw file/pixels) $\rightarrow$ Understanding Layer (OCR/tokens) $\rightarrow$ Relational Layer (evidence graph).
- An electric cyan focal node at the center emits directed edges connecting the planes, symbolizing intelligence derived from connected evidence.

```
          /\
     +---/  \---+
    /   / /\ \   \      Outer: Cryptographic Integrity Hexagon
   |   / /  \ \   |     Planes: Document, Token & Relational Layers
   |  *----O----* |     Center O: Evidence Node Network
    \  \ \  / /  /
     +---\  /---+
          \/
```

### 3.3 Typography

- **Interface & Headings:** Modern, clean, neutral sans-serif with high legibility at all optical sizes (e.g., *Inter*, *Geist Sans*, or *SF Pro Display*).
- **Data, Hashes & Code:** Monospaced, tabular-numeral fonts for SHA-256 digests, coordinates, bounding boxes, and audit timestamps (e.g., *JetBrains Mono*, *Fira Code*).
- **Weight Hierarchy:** Bold (700) for product titles and hero statements; Semi-Bold (600) for section titles and card headers; Regular (400) for long-form explanatory text.

---

## 4. Tone of Voice & Editorial Guidelines

EVIDEXA speaks with the voice of a senior digital forensic examiner and expert witness:

| Attribute | What EVIDEXA Sounds Like | What EVIDEXA Never Sounds Like |
|---|---|---|
| **Objective & Impartial** | *"Document A and Document B exhibit matching byte-level digests via SHA-256."* | *"We caught a malicious fraudster trying to submit a fake document."* |
| **Precise** | *"Bounding box [0.12, 0.45, 0.38, 0.04] indicates DCT coefficient variance exceeding standard quantization thresholds."* | *"Our AI detected massive photo manipulation."* |
| **Epistemically Honest** | *"Co-occurrence on invoice records a single billing event (INVOICED); an ongoing commercial supply relationship (SUPPLIES) cannot be inferred without contract evidence."* | *"Our engine automatically proved these companies are supply partners."* |
| **Respectful of Human Authority** | *"Candidate relationship detected with score 0.85; awaiting investigator review and corroboration."* | *"AI verdict: 99.8% Fraud Guilty."* |

---

## 5. Brand Dos and Don'ts

### DO:
- Use **EVIDEXA** in all headers, marketing copy, and official API titles.
- Pair the name with the official category: **AI-Powered Digital Forensics & Document Intelligence**.
- Emphasize provenance, explainability, chain of custody, and evidence graphs.
- Disclose pre-release development status clearly and honestly.
- Protect the integrity of original evidence at every step of processing.

### DON'T:
- Do not use colloquial abbreviations or alternative acronyms (no "EDX", "Evi-Doc", etc.).
- Do not describe EVIDEXA as an "autonomous fraud detector", "AI police", or "automated verdict engine".
- Do not make unverified claims regarding formal certifications (e.g. do not claim "certified ISO 27037 compliant" or "SOC 2 Type II certified" unless formally audited).
- Do not use generic, sensationalist AI imagery (glowing robot faces, magnifying glasses burning paper, cyber skulls).
- Do not perform risky bulk code renames that break internal database migrations or technical package structures.

