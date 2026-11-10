import React from "react";
import clsx from "clsx";

export type LogoVariant = "horizontal" | "icon" | "wordmark" | "compact";
export type LogoSize = "sm" | "md" | "lg";
export type LogoTheme = "dark" | "light";

export interface LogoProps {
  className?: string;
  variant?: LogoVariant;
  iconOnly?: boolean; // backwards-compatible alias for variant="icon"
  size?: LogoSize;
  theme?: LogoTheme;
  useImageLockup?: boolean;
}

export const Logo: React.FC<LogoProps> = ({
  className,
  variant = "horizontal",
  iconOnly = false,
  size = "md",
  theme = "dark",
  useImageLockup = false,
}) => {
  const effectiveVariant: LogoVariant = iconOnly ? "icon" : variant;

  const iconSizes = {
    sm: "w-5 h-5",
    md: "w-7 h-7",
    lg: "w-10 h-10",
  };

  const textSizes = {
    sm: "text-base",
    md: "text-xl",
    lg: "text-2xl",
  };

  const subtitleSizes = {
    sm: "text-[9px]",
    md: "text-[10px]",
    lg: "text-xs",
  };

  // If complete image lockup requested (e.g. documentation / hero display)
  if (useImageLockup && effectiveVariant !== "icon") {
    const lockupHeights = {
      sm: "h-6",
      md: "h-8",
      lg: "h-12",
    };
    return (
      <div className={clsx("inline-flex items-center select-none", className)}>
        <img
          src="/logo.png"
          alt="EVIDEXA Forensic Intelligence"
          className={clsx(
            lockupHeights[size],
            "w-auto object-contain filter drop-shadow-[0_0_12px_rgba(255,107,0,0.25)]"
          )}
        />
      </div>
    );
  }

  const isLight = theme === "light";

  return (
    <div
      className={clsx("inline-flex items-center gap-3 select-none", className)}
      role="banner"
      aria-label="EVIDEXA Brand"
    >
      {effectiveVariant !== "wordmark" && (
        <div className={clsx("relative shrink-0 flex items-center justify-center", iconSizes[size])}>
          <img
            src="/icon.png"
            alt="EVIDEXA icon"
            className="w-full h-full object-contain filter drop-shadow-[0_0_8px_rgba(255,107,0,0.35)]"
          />
        </div>
      )}

      {effectiveVariant !== "icon" && (
        <div className="flex flex-col justify-center">
          <div className={clsx("flex items-center font-sans tracking-widest leading-none", textSizes[size])}>
            <span className={clsx("font-bold tracking-widest", isLight ? "text-zinc-900" : "text-white")}>
              EVID
            </span>
            <span className="font-bold tracking-widest text-[#FF6B00]">
              EXA
            </span>
          </div>

          {effectiveVariant !== "compact" && (
            <span
              className={clsx(
                "uppercase font-mono tracking-wider font-medium mt-1 leading-none",
                subtitleSizes[size],
                isLight ? "text-zinc-600" : "text-zinc-400"
              )}
            >
              Document Intelligence
            </span>
          )}
        </div>
      )}
    </div>
  );
};
