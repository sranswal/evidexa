import React from "react";
import clsx from "clsx";
import { Loader2 } from "lucide-react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = "primary",
  size = "md",
  isLoading = false,
  disabled,
  className,
  ...props
}) => {
  const baseClasses =
    "inline-flex items-center justify-center font-medium rounded-md transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-evidexa-midnight disabled:opacity-50 disabled:cursor-not-allowed select-none";

  const sizeClasses = {
    sm: "px-2.5 py-1 text-xs gap-1.5",
    md: "px-4 py-2 text-sm gap-2",
    lg: "px-5 py-2.5 text-base gap-2.5",
  };

  const variantClasses = {
    primary:
      "bg-evidexa-cyan text-evidexa-midnight hover:bg-evidexa-aqua font-semibold focus:ring-evidexa-cyan shadow-glow hover:shadow-[0_0_20px_rgba(72,202,228,0.4)]",
    secondary:
      "bg-evidexa-charcoal text-slate-200 border border-evidexa-slate hover:bg-slate-800 hover:text-white hover:border-slate-500 focus:ring-slate-400",
    danger:
      "bg-rose-950/60 text-rose-300 border border-rose-500/50 hover:bg-rose-900/60 hover:text-white focus:ring-rose-500",
    ghost:
      "bg-transparent text-slate-300 hover:bg-evidexa-charcoal/80 hover:text-white focus:ring-slate-500",
  };

  return (
    <button
      className={clsx(baseClasses, sizeClasses[size], variantClasses[variant], className)}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && <Loader2 className="w-4 h-4 animate-spin text-current" aria-hidden="true" />}
      {children}
    </button>
  );
};

