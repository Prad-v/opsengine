import { createKeepMuiTheme } from "@/shared/ui/mui/keepMuiTheme";

describe("createKeepMuiTheme", () => {
  it("uses Keep orange as the primary color in light mode", () => {
    const theme = createKeepMuiTheme("light");
    expect(theme.palette.primary.main).toBe("#FA9E34");
    expect(theme.palette.mode).toBe("light");
  });

  it("uses dark paper backgrounds in dark mode", () => {
    const theme = createKeepMuiTheme("dark");
    expect(theme.palette.mode).toBe("dark");
    expect(theme.palette.background.paper).toBe("#111827");
  });
});
