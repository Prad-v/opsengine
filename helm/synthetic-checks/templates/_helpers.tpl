{{- define "synthetic-checks.name" -}}
synthetic-checks
{{- end -}}

{{- define "synthetic-checks.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{ .Values.fullnameOverride }}
{{- else -}}
{{ .Release.Name }}-synthetic-checks
{{- end -}}
{{- end -}}

{{- define "synthetic-checks.serviceAccountName" -}}
{{- if .Values.serviceAccount.name -}}
{{ .Values.serviceAccount.name }}
{{- else -}}
{{ include "synthetic-checks.fullname" . }}
{{- end -}}
{{- end -}}
