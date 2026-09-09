"use client";

import { useEffect, useState } from "react";
import { Button, Callout, TextInput, Title, Subtitle } from "@tremor/react";
import useSWR from "swr";
import Loading from "@/app/(keep)/loading";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { PageSubtitle } from "@/shared/ui";

interface OktaSettingsState {
  domain: string;
  issuer: string;
  client_id: string;
  client_secret: string;
  audience: string;
  jwks_url: string;
}

interface OktaSettingsResponse {
  configured: boolean;
  domain?: string | null;
  issuer?: string | null;
  client_id?: string | null;
  client_secret_set?: boolean;
  audience?: string | null;
  jwks_url?: string | null;
  auth_type?: string | null;
  frontend_env_required?: boolean;
  callback_url_hint?: string | null;
}

interface OktaSettingsFormProps {
  selected: boolean;
}

export function OktaSettingsForm({ selected }: OktaSettingsFormProps) {
  const api = useApi();
  const [settings, setSettings] = useState<OktaSettingsState>({
    domain: "",
    issuer: "",
    client_id: "",
    client_secret: "",
    audience: "",
    jwks_url: "",
  });
  const [configured, setConfigured] = useState(false);
  const [clientSecretSet, setClientSecretSet] = useState(false);
  const [authType, setAuthType] = useState<string | null>(null);
  const [shouldFetch, setShouldFetch] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const shouldFetchUrl =
    api.isReady() && shouldFetch && selected ? "/settings/auth/okta" : null;

  const { data, error, isValidating: isLoading } = useSWR<OktaSettingsResponse>(
    shouldFetchUrl,
    (url) => api.get(url),
    { revalidateOnFocus: false }
  );

  useEffect(() => {
    if (!data) return;
    setConfigured(Boolean(data.configured));
    setClientSecretSet(Boolean(data.client_secret_set));
    setAuthType(data.auth_type || null);
    setSettings({
      domain: data.domain || "",
      issuer: data.issuer || "",
      client_id: data.client_id || "",
      client_secret: "",
      audience: data.audience || "",
      jwks_url: data.jwks_url || "",
    });
    setShouldFetch(false);
  }, [data]);

  if (isLoading && shouldFetch) {
    return <Loading />;
  }

  if (error) {
    return (
      <Callout title="Error" color="rose">
        Failed to load Okta settings: {error.message}
      </Callout>
    );
  }

  const onSave = async () => {
    setErrorMessage("");
    setSuccessMessage("");
    if (!settings.domain || !settings.issuer || !settings.client_id) {
      setErrorMessage("Domain, issuer, and client ID are required");
      return;
    }
    if (!settings.client_secret && !clientSecretSet) {
      setErrorMessage("Client secret is required");
      return;
    }

    setIsSaving(true);
    try {
      const payload: Record<string, string> = {
        domain: settings.domain.trim(),
        issuer: settings.issuer.trim(),
        client_id: settings.client_id.trim(),
        audience: settings.audience.trim(),
        jwks_url: settings.jwks_url.trim(),
      };
      if (settings.client_secret) {
        payload.client_secret = settings.client_secret;
      }
      const response = await api.post("/settings/auth/okta", payload);
      setConfigured(true);
      setClientSecretSet(true);
      setSettings((prev) => ({ ...prev, client_secret: "" }));
      setSuccessMessage(
        response?.note ||
          "Okta settings saved. Set AUTH_TYPE=OKTA and matching OKTA_* env vars on the frontend, then restart."
      );
    } catch (err) {
      if (err instanceof KeepApiError) {
        setErrorMessage(err.message || "Failed to save Okta settings");
      } else {
        setErrorMessage("An unexpected error occurred");
      }
    } finally {
      setIsSaving(false);
    }
  };

  const onDelete = async () => {
    setErrorMessage("");
    setSuccessMessage("");
    setIsDeleting(true);
    try {
      await api.delete("/settings/auth/okta");
      setConfigured(false);
      setClientSecretSet(false);
      setSettings({
        domain: "",
        issuer: "",
        client_id: "",
        client_secret: "",
        audience: "",
        jwks_url: "",
      });
      setSuccessMessage("Okta settings deleted");
    } catch (err) {
      if (err instanceof KeepApiError) {
        setErrorMessage(err.message || "Failed to delete Okta settings");
      } else {
        setErrorMessage("An unexpected error occurred");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const authTypeIsOkta = (authType || "").toUpperCase() === "OKTA";

  return (
    <div className="flex flex-col gap-4 max-w-2xl">
      <div>
        <Title>Okta</Title>
        <PageSubtitle>
          Configure Okta OIDC for single sign-on. Values are stored securely and
          used by the backend immediately.
        </PageSubtitle>
      </div>

      {!authTypeIsOkta && (
        <Callout title="Frontend auth type" color="amber">
          Current AUTH_TYPE is <strong>{authType || "unset"}</strong>. To sign
          in with Okta, set <code>AUTH_TYPE=OKTA</code> on both frontend and
          backend, mirror the client ID/secret/issuer as frontend env vars, and
          restart. Callback URL:{" "}
          <code>/api/auth/callback/okta</code>
        </Callout>
      )}

      {configured && (
        <Callout title="Configured" color="teal">
          Okta settings are saved
          {clientSecretSet ? " (client secret set)" : ""}.
        </Callout>
      )}

      <div className="flex flex-col gap-3">
        <div>
          <Subtitle>Domain</Subtitle>
          <TextInput
            placeholder="https://company.okta.com"
            value={settings.domain}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, domain: e.target.value }))
            }
          />
        </div>
        <div>
          <Subtitle>Issuer</Subtitle>
          <TextInput
            placeholder="https://company.okta.com/oauth2/default"
            value={settings.issuer}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, issuer: e.target.value }))
            }
          />
        </div>
        <div>
          <Subtitle>Client ID</Subtitle>
          <TextInput
            placeholder="0oa..."
            value={settings.client_id}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, client_id: e.target.value }))
            }
          />
        </div>
        <div>
          <Subtitle>
            Client Secret
            {clientSecretSet ? " (leave blank to keep existing)" : ""}
          </Subtitle>
          <TextInput
            type="password"
            placeholder={clientSecretSet ? "••••••••" : "Client secret"}
            value={settings.client_secret}
            onChange={(e) =>
              setSettings((prev) => ({
                ...prev,
                client_secret: e.target.value,
              }))
            }
          />
        </div>
        <div>
          <Subtitle>Audience (optional)</Subtitle>
          <TextInput
            placeholder="Defaults to client ID"
            value={settings.audience}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, audience: e.target.value }))
            }
          />
        </div>
        <div>
          <Subtitle>JWKS URL (optional)</Subtitle>
          <TextInput
            placeholder="Derived from issuer when empty"
            value={settings.jwks_url}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, jwks_url: e.target.value }))
            }
          />
        </div>
      </div>

      {errorMessage && (
        <Callout title="Error" color="rose">
          {errorMessage}
        </Callout>
      )}
      {successMessage && (
        <Callout title="Success" color="teal">
          {successMessage}
        </Callout>
      )}

      <div className="flex gap-2">
        <Button color="orange" loading={isSaving} onClick={onSave}>
          Save Okta settings
        </Button>
        {configured && (
          <Button
            variant="secondary"
            color="rose"
            loading={isDeleting}
            onClick={onDelete}
          >
            Delete
          </Button>
        )}
      </div>
    </div>
  );
}
