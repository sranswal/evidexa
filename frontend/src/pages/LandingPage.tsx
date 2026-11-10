import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ShieldCheck,
  Cpu,
  Layers,
  ArrowRight,
  Fingerprint,
  AlertTriangle,
  FileText,
  Network,
  Terminal,
  Activity,
  Zap,
} from "lucide-react";
import { Logo } from "../components/brand/Logo";

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();

  // Interactive Light Table states
  const [filterMode, setFilterMode] = useState<"NORMAL" | "UV" | "BINARIZED">("NORMAL");
  const [showOcrBounds, setShowOcrBounds] = useState<boolean>(true);
  const [showVectorDiff, setShowVectorDiff] = useState<boolean>(true);

  return (
    <div className="min-h-screen bg-[#080808] text-[#FAFAFA] font-sans selection:bg-[#FF6B00] selection:text-[#080808]">
      {/* Top Precision Command Header */}
      <header className="sticky top-0 z-50 h-16 bg-[#080808]/90 backdrop-blur border-b border-[#27272A] px-6 lg:px-12 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 focus:outline-none">
            <Logo />
          </Link>
          <div className="hidden md:flex items-center gap-2 px-2.5 py-0.5 rounded bg-[#121214] border border-[#27272A] font-mono text-[11px] text-[#A1A1AA]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse" />
            <span>CORE SPEC // v4.2 COURT-READY</span>
          </div>
        </div>

        {/* Center Nav Links */}
        <nav className="hidden lg:flex items-center gap-6 text-xs font-mono text-[#A1A1AA]">
          <a href="#light-table" className="hover:text-[#FAFAFA] transition-colors">
            // LIGHT TABLE
          </a>
          <a href="#architectural-cores" className="hover:text-[#FAFAFA] transition-colors">
            // MODULES
          </a>
          <a href="#chain-of-custody" className="hover:text-[#FAFAFA] transition-colors">
            // SHA-256 AUDIT
          </a>
        </nav>

        {/* Right CTA */}
        <div className="flex items-center gap-4">
          <Link
            to="/login"
            className="text-xs font-mono uppercase tracking-wider text-[#A1A1AA] hover:text-[#FAFAFA] transition-colors px-3 py-1.5"
          >
            Sign In
          </Link>
          <Link
            to="/cases"
            className="inline-flex items-center gap-2 px-4 py-2 rounded bg-[#FF6B00] hover:bg-[#FF7E1F] text-[#080808] font-bold text-xs uppercase tracking-wider transition-all shadow-[0_0_16px_rgba(255,107,0,0.35)]"
          >
            <span>Launch Console</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      <main>
        {/* Hero Section with Tactical Technical Drafting Grid */}
        <section
          className="relative px-6 lg:px-12 py-16 lg:py-24 border-b border-[#27272A] overflow-hidden"
          style={{
            backgroundImage: "radial-gradient(#27272A 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        >
          {/* Subtle Corner Drafting Telemetry */}
          <div className="absolute top-4 left-6 hidden lg:flex items-center gap-3 font-mono text-[11px] text-[#71717A] opacity-70">
            <span>GRID: [44.02° N // 18.91° E]</span>
            <span>•</span>
            <span>SENSOR: PP-OCRv5-CALIBRATED</span>
          </div>
          <div className="absolute top-4 right-6 hidden lg:flex items-center gap-3 font-mono text-[11px] text-[#71717A] opacity-70">
            <span className="text-[#10B981]">● RETICLE_SYNC: LOCKED</span>
            <span>•</span>
            <span>TOL: ±0.0001mm</span>
          </div>

          <div className="max-w-5xl mx-auto flex flex-col items-center text-center relative z-10">
            {/* Eyebrow Tag */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-[#121214] border border-[#27272A] mb-6">
              <span className="w-2 h-2 rounded-full bg-[#FF6B00] animate-ping" />
              <span className="font-mono text-xs uppercase tracking-widest text-[#FF6B00] font-semibold">
                [ FORENSIC DOCUMENT INTELLIGENCE ]
              </span>
            </div>

            {/* Headline */}
            <h1 className="text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight uppercase leading-tight mb-6 text-[#FAFAFA]">
              The Forensic Workbench for{" "}
              <span className="text-[#FF6B00] underline decoration-[#FF6B00]/40 decoration-4 underline-offset-8">
                Serious Investigations.
              </span>
            </h1>

            {/* Subheadline */}
            <p className="max-w-2xl text-base sm:text-lg text-[#A1A1AA] mb-10 leading-relaxed font-normal">
              Turn scanned chaos, altered receipts, and foreign-script documents into court-admissible evidence. No opaque scores. Every finding links to verifiable pixels, byte hashes, and graph nodes.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center justify-center gap-4 mb-14">
              <button
                onClick={() => navigate("/cases")}
                className="inline-flex items-center gap-3 px-6 py-3.5 rounded bg-[#FF6B00] hover:bg-[#FF7E1F] text-[#080808] font-bold text-sm uppercase tracking-wider transition-all shadow-[0_0_20px_rgba(255,107,0,0.4)]"
              >
                <span>Launch Case Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              <a
                href="#light-table"
                className="inline-flex items-center gap-2 px-6 py-3.5 rounded bg-[#121214] hover:bg-[#18181B] text-[#FAFAFA] font-mono text-sm uppercase tracking-wider transition-colors border border-[#27272A]"
              >
                <Cpu className="w-4 h-4 text-[#FF6B00]" />
                <span>Inspect Digital Light Table</span>
              </a>
            </div>

            {/* Hardware Spec Strip */}
            <div className="w-full grid grid-cols-2 md:grid-cols-4 gap-2 text-left bg-[#0c0c0e] p-2 rounded-lg border border-[#27272A]">
              <div className="p-3 bg-[#121214] rounded border border-[#27272A] flex flex-col justify-between">
                <span className="font-mono text-[10px] text-[#71717A] uppercase tracking-wider mb-1">
                  OPTICAL ENGINE
                </span>
                <span className="font-mono text-xs text-[#FAFAFA] font-medium truncate">
                  PP-OCRv5 + PDFium
                </span>
              </div>

              <div className="p-3 bg-[#121214] rounded border border-[#27272A] flex flex-col justify-between">
                <span className="font-mono text-[10px] text-[#71717A] uppercase tracking-wider mb-1">
                  LATENCY SPEC
                </span>
                <div className="flex items-center gap-1.5 font-mono text-xs text-[#10B981] font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]" />
                  <span>&lt;18ms Block Resolution</span>
                </div>
              </div>

              <div className="p-3 bg-[#121214] rounded border border-[#27272A] flex flex-col justify-between">
                <span className="font-mono text-[10px] text-[#71717A] uppercase tracking-wider mb-1">
                  SANDBOX ISOLATION
                </span>
                <span className="font-mono text-xs text-[#FAFAFA] font-medium truncate">
                  Zero Cross-Tenant Leak
                </span>
              </div>

              <div className="p-3 bg-[#121214] rounded border border-[#27272A] flex flex-col justify-between">
                <span className="font-mono text-[10px] text-[#71717A] uppercase tracking-wider mb-1">
                  INTEGRITY AUDIT
                </span>
                <span className="font-mono text-xs text-[#FF6B00] font-semibold truncate">
                  SHA-256 Ledger Backed
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Interactive Digital Forensic Light Table */}
        <section id="light-table" className="px-6 lg:px-12 py-14 border-b border-[#27272A] bg-[#0c0c0e]">
          <div className="max-w-7xl mx-auto space-y-4">
            {/* Workstation Header Bar */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-[#121214] p-4 rounded-lg border border-[#27272A]">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded bg-[#FF6B00]/10 border border-[#FF6B00]/40 flex items-center justify-center text-[#FF6B00]">
                  <Activity className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm uppercase tracking-wide text-[#FAFAFA]">
                      DIGITAL FORENSIC LIGHT TABLE
                    </span>
                    <span className="px-2 py-0.5 rounded bg-red-950/60 border border-red-500/50 text-red-400 font-mono text-[10px] font-bold">
                      [TAMPER_CONFIRMED]
                    </span>
                  </div>
                  <span className="font-mono text-[11px] text-[#71717A]">
                    FILE: GST_INVOICE_IN-2026-904.PDF // PAGE_01_RAW
                  </span>
                </div>
              </div>

              {/* Interactive Layer Toggles */}
              <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
                <button
                  onClick={() =>
                    setFilterMode((prev) =>
                      prev === "NORMAL" ? "UV" : prev === "UV" ? "BINARIZED" : "NORMAL"
                    )
                  }
                  className="px-3 py-1.5 rounded bg-[#18181B] border border-[#27272A] hover:border-[#FF6B00] text-[#FAFAFA] flex items-center gap-1.5 transition-colors"
                >
                  <Zap className="w-3.5 h-3.5 text-[#FF6B00]" />
                  <span>Mode: {filterMode}</span>
                </button>

                <button
                  onClick={() => setShowOcrBounds(!showOcrBounds)}
                  className={`px-3 py-1.5 rounded border transition-colors flex items-center gap-1.5 ${
                    showOcrBounds
                      ? "bg-[#18181B] border-[#FF6B00] text-[#FF6B00]"
                      : "bg-[#121214] border-[#27272A] text-[#71717A]"
                  }`}
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>OCR Bounds</span>
                </button>

                <button
                  onClick={() => setShowVectorDiff(!showVectorDiff)}
                  className={`px-3 py-1.5 rounded border transition-colors flex items-center gap-1.5 ${
                    showVectorDiff
                      ? "bg-[#FF6B00] text-[#080808] border-[#FF6B00] font-bold"
                      : "bg-[#121214] border-[#27272A] text-[#71717A]"
                  }`}
                >
                  <Fingerprint className="w-3.5 h-3.5" />
                  <span>Vector Stream Diff</span>
                </button>
              </div>
            </div>

            {/* Tri-Pane Light Table Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
              {/* Left Telemetry Column */}
              <div className="lg:col-span-3 space-y-3 font-mono text-xs">
                <div className="p-4 bg-[#121214] rounded-lg border border-[#27272A] space-y-2">
                  <span className="text-[10px] text-[#71717A] uppercase tracking-wider block">
                    LAYER COMPOSITION
                  </span>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between p-2 rounded bg-[#080808] border border-[#27272A]">
                      <span className="text-[#FAFAFA]">Raster Bitstream</span>
                      <span className="text-[#10B981]">8bpp Grey</span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded bg-[#080808] border border-[#27272A]">
                      <span className="text-[#FAFAFA]">Vector Stream</span>
                      <span className="text-[#FF6B00]">2 Alterations</span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded bg-[#080808] border border-[#27272A]">
                      <span className="text-[#FAFAFA]">Devanagari OCR</span>
                      <span className="text-[#A1A1AA]">98.4% Acc</span>
                    </div>
                  </div>
                </div>

                <div className="p-4 bg-[#121214] rounded-lg border border-[#27272A] space-y-2">
                  <span className="text-[10px] text-[#71717A] uppercase tracking-wider block">
                    OPTICAL RETICLE LOCK
                  </span>
                  <div className="space-y-1 text-[#A1A1AA] text-[11px]">
                    <p>
                      FOCUS: <span className="text-[#FAFAFA]">X: 142.0 | Y: 388.5</span>
                    </p>
                    <p>
                      BOUNDS: <span className="text-[#FAFAFA]">W: 210.0 | H: 28.4</span>
                    </p>
                    <p>
                      DELTA: <span className="text-red-400 font-bold">+₹5,00,000.00</span>
                    </p>
                    <p>
                      COMPRESSION: <span className="text-[#FAFAFA]">JPEG DCT (Q=64 vs Q=88)</span>
                    </p>
                  </div>
                  <div className="mt-3 p-2 rounded bg-red-950/40 border border-red-500/40 text-red-300 text-[11px]">
                    Font glyph metrics for character '9' mismatch native Helvetica stream. Suspected Acrobat overlay injection.
                  </div>
                </div>
              </div>

              {/* Center Inspection Document Canvas */}
              <div
                className={`lg:col-span-6 bg-[#080808] rounded-lg border border-[#27272A] p-6 relative overflow-hidden flex flex-col justify-between transition-all ${
                  filterMode === "UV"
                    ? "filter contrast-150 saturate-50 hue-rotate-180"
                    : filterMode === "BINARIZED"
                    ? "filter grayscale contrast-200"
                    : ""
                }`}
              >
                {/* Simulated Authentic Document */}
                <div className="bg-[#101012] p-5 rounded border border-[#27272A] relative">
                  {/* Document Header */}
                  <div className="flex justify-between items-start border-b border-[#27272A] pb-3 mb-4">
                    <div>
                      <h3 className="font-bold text-sm tracking-wide text-[#FAFAFA]">
                        TAX INVOICE // कर बीजक
                      </h3>
                      <div className="font-mono text-[11px] text-[#71717A] mt-0.5">
                        GSTIN: 07AAACH7409R1ZZ • APEX LOGISTICS PVT LTD
                      </div>
                      <div className="font-mono text-[10px] text-[#A1A1AA]">
                        Plot 88, Okhla Phase III, New Delhi 110020
                      </div>
                    </div>
                    <div className="text-right font-mono text-[11px]">
                      <span className="text-[#FF6B00] font-bold block">ORIGINAL RECIPIENT</span>
                      <span className="text-[#71717A] block">DATE: 12-JAN-2026</span>
                      <span className="text-[#71717A] block">INV: APX-9941</span>
                    </div>
                  </div>

                  {/* Line Items */}
                  <div className="space-y-2 mb-4 font-mono text-xs">
                    <div className="flex justify-between text-[#71717A] border-b border-[#27272A]/60 pb-1 text-[10px]">
                      <span>DESCRIPTION / विवरण</span>
                      <span>SAC CODE</span>
                      <span>TAXABLE AMT</span>
                    </div>
                    <div className="flex justify-between text-[#FAFAFA]">
                      <span>Freight Handling (Navi Mumbai - Delhi)</span>
                      <span className="text-[#71717A]">996511</span>
                      <span>₹3,80,000.00</span>
                    </div>
                    <div className="flex justify-between text-[#FAFAFA]">
                      <span>Terminal Gate Logistics & Fuel Surcharge</span>
                      <span className="text-[#71717A]">996719</span>
                      <span>₹1,02,500.00</span>
                    </div>
                  </div>

                  {/* Total Payable Block with Crosshair Target Overlay */}
                  <div className="bg-[#141416] p-3 rounded border border-[#27272A] relative">
                    <div className="flex justify-between items-center">
                      <span className="font-mono text-xs font-semibold text-[#FAFAFA]">
                        TOTAL AMOUNT PAYABLE:
                      </span>

                      {/* Tampered Value with Reticle Highlights */}
                      <div className="relative px-2.5 py-1 rounded bg-red-950/40 border border-red-500 inline-flex items-center gap-2">
                        {/* 4 Optical Corner Brackets */}
                        <div className="absolute -top-1 -left-1 w-2 h-2 border-t-2 border-l-2 border-red-400" />
                        <div className="absolute -bottom-1 -right-1 w-2 h-2 border-b-2 border-r-2 border-red-400" />

                        {showVectorDiff && (
                          <span className="font-mono text-xs text-red-400 line-through opacity-70">
                            ₹4,82,500
                          </span>
                        )}
                        <span className="font-mono text-sm font-bold text-red-400">
                          ₹9,82,500
                        </span>
                        <AlertTriangle className="w-3.5 h-3.5 text-red-400 animate-pulse" />
                      </div>
                    </div>

                    <div className="mt-1 flex justify-between items-center text-[10px] font-mono text-[#71717A]">
                      <span>AMOUNT IN WORDS: Nine Lakh Eighty Two Thousand Five Hundred Only</span>
                      <span className="text-red-400 font-bold">[SUB-HASH MISMATCH]</span>
                    </div>
                  </div>

                  {/* Simulated OCR Bounding Box Overlays */}
                  {showOcrBounds && (
                    <div className="absolute inset-0 pointer-events-none p-5">
                      <div className="absolute top-[20px] left-[20px] w-[260px] h-[20px] border border-[#FF6B00]/40 bg-[#FF6B00]/5" />
                      <div className="absolute top-[80px] left-[20px] w-[340px] h-[16px] border border-[#10B981]/40 bg-[#10B981]/5" />
                      <div className="absolute bottom-[22px] right-[20px] w-[150px] h-[32px] border-2 border-red-500 bg-red-500/10 animate-pulse" />
                    </div>
                  )}
                </div>

                <div className="mt-4 flex items-center justify-between font-mono text-[11px] text-[#71717A] border-t border-[#27272A] pt-2">
                  <span className="text-[#FF6B00]">CROSSHAIR_ACTIVE [X: 142.0, Y: 388.5]</span>
                  <span className="text-[#10B981]">STREAM: NATIVE_PDF_COS_OBJECT_44</span>
                </div>
              </div>

              {/* Right Cryptographic Inspector Column */}
              <div className="lg:col-span-3 space-y-3 font-mono text-xs">
                <div className="p-4 bg-[#121214] rounded-lg border border-[#27272A] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-[#71717A] uppercase tracking-wider">
                      CRYPTOGRAPHIC DIGEST
                    </span>
                    <Fingerprint className="w-4 h-4 text-[#FF6B00]" />
                  </div>
                  <div className="p-2.5 bg-[#080808] rounded border border-[#27272A] text-[10px] break-all text-[#A1A1AA]">
                    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
                  </div>
                  <span className="text-[#10B981] text-[10px] font-semibold block">
                    LEGAL STATUS: COURT ADMISSIBLE (SEC 65B)
                  </span>
                </div>

                <div className="p-4 bg-[#121214] rounded-lg border border-[#27272A] space-y-2">
                  <span className="text-[10px] text-[#71717A] uppercase tracking-wider block">
                    FINDINGS LEDGER
                  </span>
                  <div className="space-y-1.5 text-[11px]">
                    <div className="p-2 rounded bg-[#080808] border-l-2 border-red-500">
                      <span className="text-red-400 font-bold block">T-01: Glyphs Injected</span>
                      <span className="text-[#71717A] text-[10px]">
                        Font 'ArialMT' injected at page stream offset 0x00412B.
                      </span>
                    </div>
                    <div className="p-2 rounded bg-[#080808] border-l-2 border-[#FF6B00]">
                      <span className="text-[#FF6B00] font-bold block">T-02: Hindi Script Validated</span>
                      <span className="text-[#71717A] text-[10px]">
                        Devanagari text matched against PP-OCRv5 dictionary.
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => navigate("/cases")}
                    className="w-full mt-3 py-2 rounded bg-[#FF6B00] hover:bg-[#FF7E1F] text-[#080808] font-bold text-xs uppercase tracking-wider transition-all"
                  >
                    Examine in Case Studio
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 4 Architectural Cores / Bento Grid */}
        <section id="architectural-cores" className="px-6 lg:px-12 py-16 border-b border-[#27272A]">
          <div className="max-w-7xl mx-auto space-y-10">
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
              <div>
                <span className="font-mono text-xs uppercase tracking-widest text-[#FF6B00]">
                  // ARCHITECTURAL CORES
                </span>
                <h2 className="text-2xl sm:text-3xl font-bold uppercase tracking-tight text-[#FAFAFA] mt-1">
                  High-Throughput Forensic Modules
                </h2>
              </div>
              <p className="text-sm text-[#A1A1AA] max-w-md">
                Zero hallucinations. Every computational process maps directly to physical bytes, font bounding descriptors, and verified corporate registry ledgers.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-4">
              {/* Module 1: Multilingual OCR Engine (7 Cols) */}
              <div className="lg:col-span-7 bg-[#121214] p-6 rounded-lg border border-[#27272A] flex flex-col justify-between group hover:border-[#FF6B00]/60 transition-colors">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <FileText className="w-5 h-5 text-[#FF6B00]" />
                      <span className="font-mono text-xs text-[#71717A] uppercase">
                        MODULE_01 // SCRIPT_PARSER
                      </span>
                    </div>
                    <span className="font-mono text-xs text-[#10B981] font-bold">
                      DEVANAGARI + LATIN
                    </span>
                  </div>
                  <h3 className="text-lg font-bold uppercase text-[#FAFAFA] mb-2">
                    Multilingual Optical Character Recognition
                  </h3>
                  <p className="text-sm text-[#A1A1AA] mb-6">
                    Simultaneous script segmentation without bounding distortion. Extracts layered typography from mixed-alphabet government circulars, bills of lading, and court orders using PP-OCRv5 and PDFium.
                  </p>

                  <div className="p-3 bg-[#080808] rounded border border-[#27272A] space-y-3 font-mono text-xs">
                    <div>
                      <div className="flex justify-between text-[#71717A] mb-1">
                        <span>DEVANAGARI SCRIPT STABILITY (हिन्दी / मराठी)</span>
                        <span className="text-[#FF6B00] font-bold">99.1%</span>
                      </div>
                      <div className="w-full bg-[#18181B] h-1.5 rounded-full overflow-hidden">
                        <div className="bg-[#FF6B00] h-full rounded-full" style={{ width: "99.1%" }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-[#71717A] mb-1">
                        <span>LATIN / NUMERIC MONOSPACE RESOLUTION</span>
                        <span className="text-[#10B981] font-bold">99.9%</span>
                      </div>
                      <div className="w-full bg-[#18181B] h-1.5 rounded-full overflow-hidden">
                        <div className="bg-[#10B981] h-full rounded-full" style={{ width: "99.9%" }} />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-6 pt-3 border-t border-[#27272A] flex items-center justify-between font-mono text-xs text-[#71717A]">
                  <span>ENGINE: PP-OCRv5-DEV-MOBILE</span>
                  <span className="text-[#FAFAFA]">ZERO-DISTORTION WARPING</span>
                </div>
              </div>

              {/* Module 2: Relational Entity Graph (5 Cols) */}
              <div className="lg:col-span-5 bg-[#121214] p-6 rounded-lg border border-[#27272A] flex flex-col justify-between group hover:border-[#FF6B00]/60 transition-colors">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Network className="w-5 h-5 text-[#FF6B00]" />
                      <span className="font-mono text-xs text-[#71717A] uppercase">
                        MODULE_02 // KNOWLEDGE_GRAPH
                      </span>
                    </div>
                    <span className="font-mono text-xs text-[#FF6B00] font-bold">
                      MULTI-CASE SCOPES
                    </span>
                  </div>
                  <h3 className="text-lg font-bold uppercase text-[#FAFAFA] mb-2">
                    Tactical Entity Mesh & Correlation
                  </h3>
                  <p className="text-sm text-[#A1A1AA] mb-4">
                    Instantly resolve shell company structures, common directors, and circular invoicing across bounded investigation scopes without cross-tenant data leakage.
                  </p>

                  <div className="h-32 bg-[#080808] rounded border border-[#27272A] flex items-center justify-center p-4 relative overflow-hidden font-mono text-xs">
                    <div className="flex items-center gap-3">
                      <div className="px-2 py-1 rounded bg-[#18181B] border border-[#27272A] text-center">
                        <span className="text-[10px] text-[#71717A] block">CASE A</span>
                        <span className="text-[#FAFAFA] font-bold">Apex Ltd</span>
                      </div>
                      <span className="text-[#FF6B00] font-bold animate-pulse">⟷ CORRELATES ⟷</span>
                      <div className="px-2 py-1 rounded bg-[#18181B] border border-[#27272A] text-center">
                        <span className="text-[10px] text-[#71717A] block">CASE B</span>
                        <span className="text-[#FF6B00] font-bold">Zenith Shell</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#27272A] flex items-center justify-between font-mono text-xs text-[#71717A]">
                  <span>LIMIT: 10,000 PAIRWISE CHECKS</span>
                  <span className="text-[#10B981] font-semibold">ANTI-ENUMERATION (404)</span>
                </div>
              </div>

              {/* Module 3: Grounded Investigator Copilot (6 Cols) */}
              <div className="lg:col-span-6 bg-[#121214] p-6 rounded-lg border border-[#27272A] flex flex-col justify-between group hover:border-[#FF6B00]/60 transition-colors">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Terminal className="w-5 h-5 text-[#FF6B00]" />
                      <span className="font-mono text-xs text-[#71717A] uppercase">
                        MODULE_03 // GROUNDED_AI
                      </span>
                    </div>
                    <span className="font-mono text-xs text-[#10B981] font-bold">
                      ZERO HALLUCINATION
                    </span>
                  </div>
                  <h3 className="text-lg font-bold uppercase text-[#FAFAFA] mb-2">
                    Deterministic Evidence Copilot
                  </h3>
                  <p className="text-sm text-[#A1A1AA] mb-4">
                    Ask natural inquiries across entire document portfolios. Every response outputs verifiable line-by-line bounding box coordinates and document tokens.
                  </p>

                  <div className="p-3 bg-[#080808] rounded border border-[#27272A] font-mono text-xs space-y-2">
                    <div className="flex items-center gap-2 text-[#71717A]">
                      <span className="text-[#FF6B00]">&gt;</span>
                      <span className="text-[#FAFAFA]">SELECT discrepancy WHERE doc='APX-9941'</span>
                    </div>
                    <div className="pl-4 border-l border-[#FF6B00]/40 text-[#A1A1AA] text-[11px] space-y-1">
                      <p className="text-[#10B981]">[MATCH FOUND] Page 1, Block 14, Line 3</p>
                      <p>Tax invoice declared ₹9,82,500. Stated items sum to ₹4,82,500.</p>
                      <p className="text-[#FF6B00]">Source: PDF_STREAM_OFFSET_0x2A19 [X:142.0, Y:388.5]</p>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#27272A] flex items-center justify-between font-mono text-xs text-[#71717A]">
                  <span>CITATION ENFORCEMENT: 100%</span>
                  <span className="text-[#FAFAFA]">EXAMINER-IN-THE-LOOP</span>
                </div>
              </div>

              {/* Module 4: Cryptographic Chain of Custody (6 Cols) */}
              <div id="chain-of-custody" className="lg:col-span-6 bg-[#121214] p-6 rounded-lg border border-[#27272A] flex flex-col justify-between group hover:border-[#FF6B00]/60 transition-colors">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-5 h-5 text-[#FF6B00]" />
                      <span className="font-mono text-xs text-[#71717A] uppercase">
                        MODULE_04 // IMMUTABILITY
                      </span>
                    </div>
                    <span className="font-mono text-xs text-[#10B981] font-bold">
                      SHA-256 LEDGER
                    </span>
                  </div>
                  <h3 className="text-lg font-bold uppercase text-[#FAFAFA] mb-2">
                    Cryptographic Chain of Custody
                  </h3>
                  <p className="text-sm text-[#A1A1AA] mb-4">
                    Every OCR ingestion, entity resolution, and review sign-off is committed to an immutable append-only hash ledger and exported into tamper-evident PDF dossiers.
                  </p>

                  <div className="p-3 bg-[#080808] rounded border border-[#27272A] font-mono text-xs space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[#71717A]">CURRENT BLOCK HASH</span>
                      <span className="text-[#10B981]">VALID [BLOCK #8412]</span>
                    </div>
                    <div className="text-[10px] text-[#A1A1AA] break-all bg-[#121214] p-2 rounded border border-[#27272A]">
                      9f81bc2476d091e779a6136e7c107a49150db20a476952232121a25c342b1302
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#27272A] flex items-center justify-between font-mono text-xs text-[#71717A]">
                  <span>STANDARDS: ISO 27037 // NIST SP 800-86</span>
                  <span className="text-[#FF6B00]">RFC 3161 READY</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Bottom Call to Action Section */}
        <section className="px-6 lg:px-12 py-16 text-center bg-[#080808]">
          <div className="max-w-3xl mx-auto space-y-6">
            <h2 className="text-2xl sm:text-4xl font-extrabold uppercase tracking-tight text-[#FAFAFA]">
              Ready to Accelerate Your Investigation?
            </h2>
            <p className="text-sm sm:text-base text-[#A1A1AA]">
              Access our full suite of digital document forensics, bilingual OCR decomposition, and cross-case intelligence.
            </p>
            <div className="pt-2">
              <button
                onClick={() => navigate("/cases")}
                className="inline-flex items-center gap-3 px-8 py-4 rounded bg-[#FF6B00] hover:bg-[#FF7E1F] text-[#080808] font-bold text-sm uppercase tracking-wider transition-all shadow-[0_0_24px_rgba(255,107,0,0.4)]"
              >
                <span>Enter Investigation Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[#27272A] bg-[#0c0c0e] px-6 lg:px-12 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 font-mono text-xs text-[#71717A]">
        <div className="flex items-center gap-2">
          <Logo iconOnly className="w-5 h-5" />
          <span>EVIDEXA FORENSIC SUITE v4.2</span>
        </div>
        <div>
          <span>DETERMINISTIC // CRYPTOGRAPHIC // AUDITED</span>
        </div>
        <div>
          <span>© 2026 EVIDEXA PLATFORM</span>
        </div>
      </footer>
    </div>
  );
};
