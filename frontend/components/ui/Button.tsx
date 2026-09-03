"use client";

import React from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "icon";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: React.ReactNode;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      icon,
      loading = false,
      disabled,
      children,
      className = "",
      ...props
    },
    ref
  ) => {
    // Consolidated ~5 button variants
    const variantStyles: Record<ButtonVariant, string> = {
      primary:
        "bg-gradient-to-r from-teal-500 to-emerald-600 hover:from-teal-400 hover:to-emerald-500 text-white font-medium shadow-md shadow-teal-500/20 border border-teal-400/30",
      secondary:
        "bg-slate-800/90 hover:bg-slate-700/90 border border-slate-700 hover:border-slate-500 text-slate-200 font-medium hover:text-white shadow-sm",
      ghost:
        "bg-transparent hover:bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-transparent",
      danger:
        "bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/40 text-rose-300 font-medium hover:border-rose-500/60",
      icon:
        "p-2 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-slate-300 hover:text-white",
    };

    const sizeStyles: Record<ButtonSize, string> = {
      sm: "h-9 min-h-[36px] px-3.5 text-xs rounded-lg gap-1.5",
      md: "px-4 py-2 text-sm rounded-xl gap-2",
      lg: "px-5 py-2.5 text-base rounded-xl gap-2.5",
    };

    const isIconOnly = variant === "icon" || (!children && Boolean(icon));

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={`inline-flex items-center justify-center transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-teal-500/40 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${
          variantStyles[variant]
        } ${isIconOnly ? "p-2 rounded-lg" : sizeStyles[size]} ${className}`}
        {...props}
      >
        {loading ? (
          <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin shrink-0" />
        ) : (
          icon && <span className="shrink-0">{icon}</span>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
