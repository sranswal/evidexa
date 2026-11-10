import React from "react";
import clsx from "clsx";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
}

export const Card: React.FC<CardProps> = ({ children, className, glow = false, ...props }) => {
  return (
    <div
      className={clsx(
        "bg-evidexa-charcoal border border-evidexa-slate/80 rounded-lg p-5 shadow-card transition-all",
        glow && "border-evidexa-cyan/40 shadow-glow",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className,
  ...props
}) => (
  <div className={clsx("flex items-center justify-between pb-3 border-b border-evidexa-slate/50 mb-4", className)} {...props}>
    {children}
  </div>
);

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  children,
  className,
  ...props
}) => (
  <h3 className={clsx("text-base font-semibold tracking-wide text-white flex items-center gap-2", className)} {...props}>
    {children}
  </h3>
);

