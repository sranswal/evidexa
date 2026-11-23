import { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw, ArrowLeft } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("EVIDEXA Workspace Error Caught by ErrorBoundary:", error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  private handleGoHome = () => {
    window.location.href = "/cases";
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[50vh] p-6 text-center">
          <div className="max-w-md w-full bg-evidexa-charcoal border border-amber-500/40 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="w-12 h-12 rounded-full bg-amber-500/15 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400">
              <AlertTriangle className="w-6 h-6" />
            </div>

            <div>
              <h3 className="text-base font-semibold text-white">Workspace View Recovered</h3>
              <p className="text-xs text-slate-400 mt-1">
                A rendering anomaly occurred, but the investigation workspace caught it safely.
              </p>
              {this.state.error?.message && (
                <div className="mt-2.5 p-2 bg-slate-900 border border-slate-800 rounded font-mono text-[11px] text-rose-300 break-words text-left">
                  {this.state.error.message}
                </div>
              )}
            </div>

            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                type="button"
                onClick={this.handleReset}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-white text-xs font-medium rounded-md border border-slate-600 transition cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry View</span>
              </button>

              <button
                type="button"
                onClick={this.handleGoHome}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-evidexa-cyan/20 hover:bg-evidexa-cyan/30 text-evidexa-cyan text-xs font-semibold rounded-md border border-evidexa-cyan/50 transition cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Return to Cases</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
