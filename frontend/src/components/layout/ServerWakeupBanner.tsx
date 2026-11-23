import React, { useState, useEffect } from "react";
import { Zap, CheckCircle2, RefreshCw } from "lucide-react";
import { BASE_URL } from "../../api/client";

export const ServerWakeupBanner: React.FC = () => {
  const [status, setStatus] = useState<"checking" | "waking" | "online" | "hidden">("checking");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    let pollInterval: NodeJS.Timeout | null = null;
    let isMounted = true;

    // Determine target healthcheck URL (falls back to origin/health or BASE_URL/../health)
    const healthUrl = BASE_URL.endsWith("/api/v1")
      ? BASE_URL.replace("/api/v1", "/health")
      : `${BASE_URL}/health`;

    // Flag as 'waking' if server takes more than 2.2 seconds to respond
    timer = setTimeout(() => {
      if (isMounted && status === "checking") {
        setStatus("waking");
      }
    }, 2200);

    const checkHealth = async () => {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000);
        const res = await fetch(healthUrl, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (res.ok && isMounted) {
          if (timer) clearTimeout(timer);
          if (pollInterval) clearInterval(pollInterval);
          setStatus("online");
          setTimeout(() => {
            if (isMounted) setStatus("hidden");
          }, 4000);
        }
      } catch {
        if (isMounted) {
          setStatus("waking");
        }
      }
    };

    checkHealth();

    // Poll every 5s while waking up
    pollInterval = setInterval(() => {
      if (status === "waking") {
        checkHealth();
      }
    }, 5000);

    const elapsedTimer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => {
      isMounted = false;
      if (timer) clearTimeout(timer);
      if (pollInterval) clearInterval(pollInterval);
      clearInterval(elapsedTimer);
    };
  }, [status]);

  if (status === "hidden" || status === "checking") {
    return null;
  }

  if (status === "online") {
    return (
      <div className="bg-emerald-950/90 border-b border-emerald-500/50 text-emerald-200 px-4 py-2 text-xs font-medium flex items-center justify-center gap-2 transition-all duration-500 animate-fadeIn shadow-lg sticky top-0 z-50">
        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
        <span>Forensic Engine is Online & Fully Operational</span>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-r from-amber-950/95 via-slate-900/95 to-amber-950/95 border-b border-amber-500/40 text-amber-200 px-4 py-2.5 text-xs font-medium flex flex-wrap items-center justify-center gap-3 shadow-lg sticky top-0 z-50 backdrop-blur-md">
      <div className="flex items-center gap-2">
        <Zap className="w-4 h-4 text-amber-400 animate-pulse shrink-0" />
        <span className="font-semibold text-amber-300">
          Forensic Engine waking up from eco-sleep (~30–45s)
        </span>
      </div>
      <div className="flex items-center gap-2 text-amber-200/80">
        <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-400" />
        <span>Render container initializing ({elapsedSeconds}s elapsed). Feel free to explore while it boots!</span>
      </div>
    </div>
  );
};
