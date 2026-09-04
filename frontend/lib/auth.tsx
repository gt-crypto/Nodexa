"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

export type DemoRole =
  | "Finance Operations Analyst"
  | "Finance Controller"
  | "Risk & Compliance Analyst"
  | "Finance Operations Manager";

export interface DemoUser {
  email: string;
  role: DemoRole;
  name: string;
  initials: string;
  department: string;
  primaryResponsibilities: string[];
  highlightRoutes: string[];
}

export const DEMO_PASSWORD = "SentinelDemo123!";

export const DEMO_USERS: Record<string, DemoUser> = {
  "finance@nodalsentinel.demo": {
    email: "finance@nodalsentinel.demo",
    role: "Finance Operations Analyst",
    name: "Alex Kumar",
    initials: "AK",
    department: "Settlement Operations",
    primaryResponsibilities: [
      "Exception investigation",
      "Controller monitoring",
      "Pattern analysis",
      "Merchant analysis",
      "Data injection/demo scenarios",
    ],
    highlightRoutes: ["/copilot", "/patterns", "/trust-score", "/injection"],
  },
  "controller@nodalsentinel.demo": {
    email: "controller@nodalsentinel.demo",
    role: "Finance Controller",
    name: "Elena Rostova",
    initials: "ER",
    department: "Financial Controls & Invariants",
    primaryResponsibilities: [
      "Exception review",
      "Remediation approval",
      "Verification",
      "Financial exposure",
      "Audit trail",
    ],
    highlightRoutes: ["/", "/verifier", "/architecture"],
  },
  "risk@nodalsentinel.demo": {
    email: "risk@nodalsentinel.demo",
    role: "Risk & Compliance Analyst",
    name: "Marcus Vance",
    initials: "MV",
    department: "Risk Management",
    primaryResponsibilities: [
      "High-risk cases",
      "Trust scores",
      "Drift monitoring",
      "Audit evidence",
      "Escalations",
    ],
    highlightRoutes: ["/trust-score", "/drift-radar", "/escalations"],
  },
  "manager@nodalsentinel.demo": {
    email: "manager@nodalsentinel.demo",
    role: "Finance Operations Manager",
    name: "Priya Sharma",
    initials: "PS",
    department: "Executive Operations",
    primaryResponsibilities: [
      "Business impact",
      "Overall controller performance",
      "Exception volumes",
      "Financial exposure",
      "Operational metrics",
    ],
    highlightRoutes: ["/", "/benchmark", "/drift-radar"],
  },
};

const AUTH_STORAGE_KEY = "nodal_sentinel_demo_session_v1";
const SESSION_TTL_MS = 24 * 60 * 60 * 1000; // 24-hour session expiration

/**
 * Reads the current demo user from localStorage (safe in SSR).
 * Validates session expiration against 24-hour TTL.
 */
export function getCurrentUser(): DemoUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);

    // Validate session expiration timestamp
    if (parsed && parsed.authenticatedAt) {
      const authTime = new Date(parsed.authenticatedAt).getTime();
      if (!isNaN(authTime) && Date.now() - authTime > SESSION_TTL_MS) {
        localStorage.removeItem(AUTH_STORAGE_KEY);
        return null;
      }
    }

    if (parsed && parsed.email && DEMO_USERS[parsed.email.toLowerCase()]) {
      return DEMO_USERS[parsed.email.toLowerCase()];
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Returns true if an authenticated demo session is currently active.
 */
export function isAuthenticated(): boolean {
  return getCurrentUser() !== null;
}

export interface AuthResult {
  success: boolean;
  error?: string;
  user?: DemoUser;
}

/**
 * Validates demo credentials and persists the session if valid.
 */
export function login(email: string, password: string): AuthResult {
  const cleanEmail = email.trim().toLowerCase();
  const cleanPassword = password.trim();

  if (!cleanEmail || !cleanPassword) {
    return {
      success: false,
      error: "Please enter both work email and password.",
    };
  }

  const demoUser = DEMO_USERS[cleanEmail];
  if (!demoUser || cleanPassword !== DEMO_PASSWORD) {
    return {
      success: false,
      error: "Invalid demo credentials. Use one of the demo accounts.",
    };
  }

  if (typeof window !== "undefined") {
    localStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({
        email: demoUser.email,
        role: demoUser.role,
        authenticatedAt: new Date().toISOString(),
      })
    );
    window.dispatchEvent(new Event("auth-change"));
  }

  return {
    success: true,
    user: demoUser,
  };
}

/**
 * Clears the demo session.
 */
export function logout(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    window.dispatchEvent(new Event("auth-change"));
  }
}

// ─── React Context & Hook for Reactive Components ───────────────────────────

interface AuthContextType {
  user: DemoUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => AuthResult;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  login: () => ({ success: false }),
  logout: () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<DemoUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const syncAuth = () => {
    const current = getCurrentUser();
    setUser(current);
    setIsLoading(false);
  };

  useEffect(() => {
    syncAuth();

    const handleStorage = () => syncAuth();
    window.addEventListener("storage", handleStorage);
    window.addEventListener("auth-change", handleStorage);

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("auth-change", handleStorage);
    };
  }, []);

  const handleLogin = (email: string, password: string): AuthResult => {
    const result = login(email, password);
    if (result.success && result.user) {
      setUser(result.user);
    }
    return result;
  };

  const handleLogout = () => {
    logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        login: handleLogin,
        logout: handleLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => useContext(AuthContext);
