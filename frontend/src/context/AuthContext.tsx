import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import type { User } from "../types/api";
import { fetchCurrentUser, loginUser, logoutUser, refreshSession } from "../api/auth";
import { setOnUnauthorized, getAccessToken } from "../api/client";

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (usernameOrEmail: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = useCallback(async () => {
    try {
      await logoutUser();
    } catch {
      // Ignored
    } finally {
      setUser(null);
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const tokenRes = await refreshSession();
      setUser(tokenRes.user);
    } catch {
      setUser(null);
    }
  }, []);

  const login = useCallback(async (usernameOrEmail: string, password: string) => {
    setIsLoading(true);
    try {
      const tokenRes = await loginUser(usernameOrEmail, password);
      setUser(tokenRes.user);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    setOnUnauthorized(() => {
      setUser(null);
    });

    // Check existing session
    const initAuth = async () => {
      try {
        if (!getAccessToken()) {
          // Attempt silent cookie refresh on page reload
          const tokenRes = await refreshSession();
          setUser(tokenRes.user);
        } else {
          const profile = await fetchCurrentUser();
          setUser(profile);
        }
      } catch {
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    void initAuth();
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    refresh,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    return {
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: async () => {},
      logout: async () => {},
      refresh: async () => {},
    };
  }
  return context;
}
