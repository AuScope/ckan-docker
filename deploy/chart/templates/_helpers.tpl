{{/*
Expand the name of the chart.
*/}}
{{- define "ckan-helm.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "ckan-helm.postgresql.fullname" -}}
{{- printf "%s-%s-%s" .Values.global.appName .Release.Name "postgresql" | trunc 63 | trimSuffix "-" -}}
{{- end -}}


{{- define "ckan-helm.redis.fullname" -}}
{{- printf "%s-%s-%s" .Values.global.appName .Release.Name "redis" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ckan-helm.solr.fullname" -}}
{{- printf "%s-%s-%s" .Values.global.appName .Release.Name "solr" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ckan-helm.datapusher.fullname" -}}
{{- printf "%s-%s-%s" .Values.global.appName .Release.Name "datapusher" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ckan-helm.ckan.fullname" -}}
{{- printf "%s-%s-%s" .Values.global.appName .Release.Name "ckan" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ckan-helm.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ckan-helm.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ckan-helm.labels" -}}
helm.sh/chart: {{ include "ckan-helm.chart" . }}
{{ include "ckan-helm.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ckan-helm.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ckan-helm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "ckan-helm.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ckan-helm.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
