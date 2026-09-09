"use client";

import { ReactNode, useEffect, useMemo, useState } from "react";
import { ThemeProvider } from "@mui/material";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v15-appRouter";
import { LOCALSTORAGE_THEME_KEY } from "@/shared/constants";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { createKeepMuiTheme } from "./keepMuiTheme";

type MuiProviderProps = {
  children: ReactNode;
};

function resolveMode(
  themePreference: "light" | "dark" | null,
  systemPrefersDark: boolean
): "light" | "dark" {
  if (themePreference === "light" || themePreference === "dark") {
    return themePreference;
  }
  return systemPrefersDark ? "dark" : "light";
}

export function MuiProvider({ children }: MuiProviderProps) {
  const [themePreference] = useLocalStorage<"light" | "dark" | null>(
    LOCALSTORAGE_THEME_KEY,
    null
  );
  const [systemPrefersDark, setSystemPrefersDark] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    setSystemPrefersDark(mediaQuery.matches);
    const onChange = (event: MediaQueryListEvent) => {
      setSystemPrefersDark(event.matches);
    };
    mediaQuery.addEventListener("change", onChange);
    return () => mediaQuery.removeEventListener("change", onChange);
  }, []);

  const mode = resolveMode(themePreference, systemPrefersDark);
  const theme = useMemo(() => createKeepMuiTheme(mode), [mode]);

  // CssBaseline is intentionally omitted so Tailwind + Tremor styles elsewhere
  // are not reset while we migrate pages incrementally to MUI.
  return (
    <AppRouterCacheProvider options={{ enableCssLayer: true }}>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </AppRouterCacheProvider>
  );
}
