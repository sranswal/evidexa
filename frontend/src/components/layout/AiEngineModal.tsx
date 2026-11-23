import React, { useState, useEffect } from "react";
import {
  Zap,
  CheckCircle2,
  AlertTriangle,
  Eye,
  EyeOff,
  Cpu,
  Globe,
  Lock,
} from "lucide-react";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { aiConfigApi, type AiConfigData } from "../../api/aiConfig";

interface AiEngineModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentConfig?: AiConfigData | null;
  onConfigUpdated: () => void;
}

export const AiEngineModal: React.FC<AiEngineModalProps> = ({
  isOpen,
  onClose,
  currentConfig,
  onConfigUpdated,
}) => {
  const [mode, setMode] = useState<"OFFLINE" | "ONLINE">("OFFLINE");
  const [model, setModel] = useState<string>("gemini-3.8-flash");
  const [apiKey, setApiKey] = useState<string>("");
  const [showKey, setShowKey] = useState<boolean>(false);

  // Testing & Saving States
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message?: string;
    latency_ms?: number;
    error?: string;
  } | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (currentConfig) {
      setMode(currentConfig.mode || "OFFLINE");
      const defaultModel =
        currentConfig.model &&
        !currentConfig.model.includes("2.5") &&
        !currentConfig.model.includes("2.0") &&
        !currentConfig.model.includes("1.5")
          ? currentConfig.model
          : "gemini-3.8-flash";
      setModel(defaultModel);
      setTestResult(null);
      setSaveError(null);
    }
  }, [currentConfig, isOpen]);

  const handleTestConnection = async () => {
    if (!apiKey.trim() && !currentConfig?.has_key) {
      setTestResult({
        success: false,
        error: "Please enter a Google Gemini API key to test.",
      });
      return;
    }

    setIsTesting(true);
    setTestResult(null);
    setSaveError(null);

    try {
      const keyToTest = apiKey.trim() || "";
      const res = await aiConfigApi.testKey(keyToTest, model);
      if (res.success) {
        setTestResult({
          success: true,
          message: res.message || `Successfully connected to ${model}`,
          latency_ms: res.latency_ms,
        });
      } else {
        setTestResult({
          success: false,
          error: res.error || "Connection test failed. Please verify key.",
        });
      }
    } catch (err: any) {
      setTestResult({
        success: false,
        error: err.message || "Network error while connecting to Gemini API.",
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveError(null);

    try {
      const payload = {
        mode,
        provider: "gemini",
        model,
        api_key: apiKey.trim() ? apiKey.trim() : undefined,
        validate: mode === "ONLINE" && Boolean(apiKey.trim()),
      };

      const res = await aiConfigApi.updateConfig(payload);
      if (res.success) {
        onConfigUpdated();
        onClose();
      } else {
        setSaveError(res.error || "Failed to update AI configuration.");
      }
    } catch (err: any) {
      setSaveError(err.message || "Failed to update configuration.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="AI Operating Engine & Multimodal Intelligence"
    >
      <div className="space-y-5 text-sm">
        {/* Mode Selector Toggle */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Select AI Operating Mode
            </span>
            <span className="text-[11px] text-slate-400 font-mono">
              Current: <strong className={mode === "ONLINE" ? "text-evidexa-cyan" : "text-slate-300"}>{mode}</strong>
            </span>
          </div>

          <div className="p-1.5 bg-evidexa-midnight border border-evidexa-slate rounded-lg grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => {
                setMode("OFFLINE");
                setTestResult(null);
              }}
              className={`flex items-center justify-center gap-2 py-3 px-3 rounded-md font-semibold text-xs transition-all cursor-pointer ${
                mode === "OFFLINE"
                  ? "bg-slate-800 text-white border border-slate-600 shadow-md"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border border-transparent"
              }`}
            >
              <Lock className="w-4 h-4 text-slate-400" />
              <span>Offline (Air-Gapped)</span>
            </button>

            <button
              type="button"
              onClick={() => setMode("ONLINE")}
              className={`flex items-center justify-center gap-2 py-3 px-3 rounded-md font-semibold text-xs transition-all cursor-pointer ${
                mode === "ONLINE"
                  ? "bg-evidexa-cyan/25 border border-evidexa-cyan text-evidexa-cyan shadow-[0_0_15px_rgba(72,202,228,0.35)]"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border border-transparent"
              }`}
            >
              <Zap className={`w-4 h-4 text-evidexa-cyan ${mode === "ONLINE" ? "animate-pulse" : ""}`} />
              <span>Online (Google Gemini AI)</span>
            </button>
          </div>
        </div>

        {/* Operating Description */}
        {mode === "OFFLINE" ? (
          <div className="p-3.5 bg-slate-900/60 border border-slate-700/60 rounded-md flex flex-col gap-2 text-xs text-slate-300">
            <div className="flex items-start gap-3">
              <Cpu className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-white block mb-0.5">Air-Gapped Deterministic Mode Active</strong>
                Zero network calls. Relies exclusively on local ONNX neural OCR, PikePDF structural
                checks, 2D-DCT copy-move mathematics, and strict decimal accounting rules.
              </div>
            </div>
            <div className="pt-2 border-t border-slate-800 flex justify-end">
              <button
                type="button"
                onClick={() => setMode("ONLINE")}
                className="text-xs font-medium text-evidexa-cyan hover:underline flex items-center gap-1 cursor-pointer"
              >
                <span>Switch to Online Mode to enter Gemini API Key & select model</span>
                <Zap className="w-3.5 h-3.5 text-evidexa-cyan" />
              </button>
            </div>
          </div>
        ) : (
          <div className="p-3 bg-evidexa-cyan/10 border border-evidexa-cyan/30 rounded-md flex items-start gap-3 text-xs text-slate-300">
            <Globe className="w-5 h-5 text-evidexa-cyan shrink-0 mt-0.5" />
            <div>
              <strong className="text-evidexa-cyan block mb-0.5">Online Multimodal AI Mode</strong>
              Activates <strong>Google Gemini Vision</strong> for pixel-level visual tampering
              detection, subtle font baseline discrepancies, forged stamp verification, and dynamic
              investigative conversational intelligence in the AI Assistant.
            </div>
          </div>
        )}

        {/* Online Configuration Options */}
        {mode === "ONLINE" && (
          <div className="space-y-4 pt-1 border-t border-evidexa-slate/60">
            {/* Model Selection Dropdown */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Target Gemini Model
              </label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full bg-evidexa-midnight border border-evidexa-slate rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-evidexa-cyan"
              >
                {currentConfig?.available_models && currentConfig.available_models.length > 0 ? (
                  currentConfig.available_models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="gemini-3.8-flash">
                      Gemini 3.8 Flash (Recommended - Fastest Multimodal Forensics)
                    </option>
                    <option value="gemini-3.8-flash-lite">
                      Gemini 3.8 Flash-Lite (High-Throughput & Fast)
                    </option>
                    <option value="gemini-3.6-flash">
                      Gemini 3.6 Flash (Stable Multimodal)
                    </option>
                    <option value="gemini-3.5-flash-lite">
                      Gemini 3.5 Flash-Lite (Lightweight Extraction)
                    </option>
                  </>
                )}
              </select>
            </div>

            {/* API Key Input */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Google Gemini API Key
                </label>
                {currentConfig?.has_key && (
                  <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    Key configured ({currentConfig.masked_key})
                  </span>
                )}
              </div>

              <div className="relative">
                <input
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={
                    currentConfig?.has_key
                      ? "Enter new key to replace configured key..."
                      : "Paste your Gemini API key (AIzaSy...)"
                  }
                  className="w-full bg-evidexa-midnight border border-evidexa-slate rounded-md px-3 py-2 pr-10 text-sm text-white placeholder-slate-500 font-mono focus:outline-none focus:ring-1 focus:ring-evidexa-cyan"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-2.5 top-2.5 text-slate-400 hover:text-white"
                >
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Keys are held in encrypted session memory and used strictly for examiner-initiated
                actions. Never written to permanent disk storage.
              </p>
            </div>

            {/* Test Connection Button & Result */}
            <div className="flex items-center justify-between pt-1">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={handleTestConnection}
                isLoading={isTesting}
                disabled={isTesting || (!apiKey.trim() && !currentConfig?.has_key)}
              >
                {isTesting ? "Testing Ping..." : "Test Connection"}
              </Button>

              {testResult && (
                <div
                  className={`text-xs flex items-center gap-1.5 font-medium ${
                    testResult.success ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {testResult.success ? (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>{testResult.message}</span>
                      {testResult.latency_ms && (
                        <span className="font-mono text-[10px] text-slate-400">
                          ({testResult.latency_ms}ms)
                        </span>
                      )}
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span className="truncate max-w-xs">{testResult.error}</span>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Error message */}
        {saveError && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded text-xs text-rose-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{saveError}</span>
          </div>
        )}

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-evidexa-slate">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={handleSave}
            isLoading={isSaving}
            disabled={isSaving}
          >
            {mode === "ONLINE" ? "Save & Activate Online AI" : "Save Mode"}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
