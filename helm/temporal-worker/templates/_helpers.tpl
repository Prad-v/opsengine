{{- define "temporal-worker.fullname" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "temporal-worker.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "temporal-worker.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
