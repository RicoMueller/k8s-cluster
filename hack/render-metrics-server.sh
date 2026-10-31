#!/usr/bin/env bash
# Rendert infrastructure/controllers/metrics-server/metrics-server.yaml aus dem
# offiziellen Helm-Chart (Pantheon-Konvention: helm template, kein helm install).
#
# Einzige Quelle fuer die Versionen ist dieses Skript. Renovate hebt die
# Variablen unten an und fuehrt das Skript danach als postUpgradeTask aus,
# sodass der PR das fertig gerenderte Manifest enthaelt.
# Lokal genauso aufrufbar:  bash hack/render-metrics-server.sh
set -euo pipefail

# renovate: datasource=helm depName=metrics-server registryUrl=https://kubernetes-sigs.github.io/metrics-server/
CHART_VERSION="3.14.0"
# renovate: datasource=docker depName=registry.k8s.io/metrics-server/metrics-server
IMAGE_TAG="v0.9.1"
# renovate: datasource=github-releases depName=helm/helm
HELM_VERSION="v4.3.1"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${REPO_ROOT}/infrastructure/controllers/metrics-server/metrics-server.yaml"

# Im Renovate-Container (containerbase) ist helm nicht vorinstalliert.
if ! command -v helm >/dev/null 2>&1; then
  if command -v install-tool >/dev/null 2>&1; then
    install-tool helm "${HELM_VERSION#v}"
  else
    echo "helm nicht gefunden (und kein install-tool verfuegbar)" >&2
    exit 1
  fi
fi

TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT

{
  echo "# GENERIERT von hack/render-metrics-server.sh - nicht von Hand bearbeiten."
  echo "# Chart metrics-server ${CHART_VERSION}, Image ${IMAGE_TAG}"
  # --kubelet-insecure-tls: Talos-Kubelets haben kein von der Cluster-CA
  # signiertes Serving-Zertifikat (siehe rezept-homepage, Teil A).
  helm template metrics-server metrics-server \
    --repo https://kubernetes-sigs.github.io/metrics-server/ \
    --version "${CHART_VERSION}" \
    --namespace kube-system \
    --set 'args={--kubelet-insecure-tls}' \
    --set image.tag="${IMAGE_TAG}"
} > "${TMP}"

cat "${TMP}" > "${OUT}"
echo "gerendert: ${OUT#"${REPO_ROOT}/"} (Chart ${CHART_VERSION}, Image ${IMAGE_TAG})"
