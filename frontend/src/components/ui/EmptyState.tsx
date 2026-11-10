import React from "react";
import { FolderSearch } from "lucide-react";
import clsx from "clsx";

export interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  action,
  className,
}) => {
  return (
    <div
      className={clsx(
        "flex flex-col items-center justify-center p-8 text-center border border-dashed border-evidexa-slate rounded-lg bg-evidexa-midnight/40",
        className
      )}
    >
      <div className="p-3 bg-slate-800/60 rounded-full text-slate-400 mb-3">
        {icon || <FolderSearch className="w-8 h-8 text-slate-400" aria-hidden="true" />}
      </div>
      <h4 className="text-base font-semibold text-slate-200">{title}</h4>
      <p className="text-sm text-slate-400 mt-1 max-w-md">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
};

