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
    // Enterprise fintech button styles - sharp, high contrast, subtle borders
    const variantStyles: Record<ButtonVariant, string> = {
      primary:
        "bg-sky-600 hover:bg-sky-500 active:bg-sky-700 text-white font-medium border border-sky-500/60 shadow-sm transition-colors",
      secondary:
        "bg-[#111726] hover:bg-[#161f33] active:bg-[#0e1422] border border-slate-800 hover:border-slate-700 text-slate-200 font-medium hover:text-white shadow-sm transition-colors",
      ghost:
        "bg-transparent hover:bg-slate-800/60 active:bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-transparent transition-colors",
      danger:
        "bg-rose-950/40 hover:bg-rose-900/50 border border-rose-800/50 text-rose-300 font-medium hover:border-rose-700 transition-colors",
      icon:
        "p-1.5 rounded-lg bg-[#111726] hover:bg-[#161f33] border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white transition-colors",
    };

    const sizeStyles: Record<ButtonSize, string> = {
      sm: "h-8 px-2.5 text-xs rounded-md gap-1.5",
      md: "h-9 px-3.5 text-xs rounded-lg gap-2",
      lg: "h-10 px-4 text-sm rounded-lg gap-2.5",
    };

    const isIconOnly = variant === "icon" || (!children && Boolean(icon));

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={`inline-flex items-center justify-center font-sans select-none focus:outline-none focus:ring-1 focus:ring-sky-500/50 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${
          variantStyles[variant]
        } ${isIconOnly ? "p-2 rounded-lg" : sizeStyles[size]} ${className}`}
        {...props}
      >
        {loading ? (
          <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin shrink-0" />
        ) : (
          icon && <span className="shrink-0">{icon}</span>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
