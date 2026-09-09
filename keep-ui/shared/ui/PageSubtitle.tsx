import { Typography } from "@mui/material";

export const PageSubtitle = ({ children }: { children: React.ReactNode }) => {
  return (
    <Typography variant="subtitle1" color="text.secondary">
      {children}
    </Typography>
  );
};
