import { Fragment } from "react";
import { Button, Typography, Stack } from "@mui/material";

interface Props {
  setIsFormOpen: (value: boolean) => void;
}

export const IncidentListPlaceholder = ({ setIsFormOpen }: Props) => {
  const onCreateButtonClick = () => {
    setIsFormOpen(true);
  };

  return (
    <Fragment>
      <Stack
        alignItems="center"
        justifyContent="center"
        spacing={4}
        sx={{ height: "100%", textAlign: "center" }}
      >
        <Stack spacing={1.5}>
          <Typography variant="h5">No Incidents Yet</Typography>
          <Typography variant="body2" color="text.secondary">
            Create incidents manually to enable AI detection
          </Typography>
        </Stack>
        <Button
          color="primary"
          variant="contained"
          sx={{ mb: 5 }}
          onClick={() => onCreateButtonClick()}
        >
          Create Incident
        </Button>
      </Stack>
    </Fragment>
  );
};
