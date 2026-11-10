import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "./Button";
import clsx from "clsx";

export interface ErrorMessageProps {
  title?: string;
  message: string;
  code?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  title = "Failed to load data",
  message,
  code,
  onRetry,
  className,
}) => {
  return (
    <div
      role="alert"
      className={clsx(
        "p-5 rounded-lg border border-rose-500/40 bg-rose-950/30 text-slate-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4",
        className
      )}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-rose-400 mt-0.5 shrink-0" aria-hidden="true" />
        <div>
          <div className="flex items-center gap-2">
            <h4 className="font-semibold text-rose-200 text-sm">{title}</h4>
            {code && (
              <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800">
                {code}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-300 mt-1">{message}</p>
        </div>
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry} className="shrink-0 self-end sm:self-auto">
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Retry
        </Button>
      )}
    </div>
  );
};

