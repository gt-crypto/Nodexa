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
    // Premium fintech button styles (Mercury/Ramp inspired)
    const variantStyles: Record<ButtonVariant, string> = {
      primary:
        "btn-primary-cta bg-[#F4D35E] hover:bg-[#E8C84A] active:bg-[#DDBA35] text-slate-950 font-semibold border border-[#E8C84A] shadow-xs transition-colors focus:ring-2 focus:ring-[#F4D35E]/40",
      secondary:
        "bg-white hover:bg-slate-50 active:bg-slate-100 border border-slate-200 hover:border-slate-300 text-slate-700 hover:text-slate-900 font-medium shadow-xs transition-colors focus:ring-2 focus:ring-slate-200",
      ghost:
        "bg-transparent hover:bg-slate-100 active:bg-slate-200 text-slate-600 hover:text-slate-900 border border-transparent transition-colors",
      danger:
        "bg-rose-50 hover:bg-rose-100 active:bg-rose-200 border border-rose-200 text-rose-700 font-medium transition-colors focus:ring-2 focus:ring-rose-500/20",
      icon:
        "p-1.5 rounded-lg bg-white hover:bg-slate-50 active:bg-slate-100 border border-slate-200 hover:border-slate-300 text-slate-600 hover:text-slate-900 shadow-xs transition-colors",
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
        data-variant={variant}
        disabled={disabled || loading}
        className={`inline-flex items-center justify-center font-sans select-none focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${
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
