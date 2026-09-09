import { Typography } from "@mui/material";
import clsx from "clsx";

export const PageTitle = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  return (
    <Typography
      variant="h4"
      component="h1"
      className={clsx("line-clamp-2", className)}
    >
      {children}
    </Typography>
  );
};
