"use client";

import { createTheme, ThemeOptions } from "@mui/material/styles";

const keepOrange = {
  main: "#FA9E34",
  light: "#FFB65C",
  dark: "#E8841A",
  contrastText: "#ffffff",
};

const sharedTypography: ThemeOptions["typography"] = {
  fontFamily: "inherit",
  h4: {
    fontWeight: 600,
    fontSize: "1.25rem",
    lineHeight: 1.4,
  },
  subtitle1: {
    fontSize: "0.875rem",
    lineHeight: 1.5,
  },
  button: {
    textTransform: "none",
    fontWeight: 500,
  },
};

export function createKeepMuiTheme(mode: "light" | "dark") {
  const isDark = mode === "dark";

  return createTheme({
    palette: {
      mode,
      primary: keepOrange,
      warning: keepOrange,
      background: {
        default: isDark ? "#0b1220" : "#f9fafb",
        paper: isDark ? "#111827" : "#ffffff",
      },
      text: {
        primary: isDark ? "#f3f4f6" : "#111827",
        secondary: isDark ? "#9ca3af" : "#4b5563",
      },
      divider: isDark ? "#1f2937" : "#e5e7eb",
    },
    typography: sharedTypography,
    shape: {
      borderRadius: 8,
    },
    components: {
      MuiButton: {
        defaultProps: {
          disableElevation: true,
        },
        styleOverrides: {
          root: {
            borderRadius: 8,
          },
          containedPrimary: {
            backgroundColor: keepOrange.main,
            "&:hover": {
              backgroundColor: keepOrange.dark,
            },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: 6,
          },
        },
      },
      MuiPaper: {
        defaultProps: {
          elevation: 0,
        },
        styleOverrides: {
          root: {
            backgroundImage: "none",
            border: `1px solid ${isDark ? "#1f2937" : "#e5e7eb"}`,
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            borderColor: isDark ? "#1f2937" : "#e5e7eb",
          },
          head: {
            fontWeight: 600,
            backgroundColor: isDark ? "#111827" : "#ffffff",
          },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            "&:nth-of-type(even)": {
              backgroundColor: isDark
                ? "rgba(255,255,255,0.02)"
                : "rgba(0,0,0,0.02)",
            },
          },
        },
      },
    },
  });
}
