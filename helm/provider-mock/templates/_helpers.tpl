{{- define "provider-mock.fullname" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "provider-mock.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "provider-mock.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
