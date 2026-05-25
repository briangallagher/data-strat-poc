#!/bin/bash
# Inject OPENLINEAGE_NAMESPACE into all KFP pipeline pods via the DSP workflow controller
# Adapted from rh-waterford-et/lineage-demo-pipeline deploy-dsp.sh
#
# This patches the Argo workflow controller ConfigMap so every pipeline pod
# gets OPENLINEAGE_NAMESPACE set to its own Kubernetes namespace (via downward API).
# No hardcoding needed -- works correctly in any namespace.
#
# Usage: ./inject-openlineage-namespace.sh [namespace]

set -e

NAMESPACE="${1:-data-strat-poc}"
CONFIGMAP="ds-pipeline-workflow-controller-dspa"

echo "Patching $CONFIGMAP in $NAMESPACE to inject OPENLINEAGE_NAMESPACE..."

oc patch configmap "$CONFIGMAP" -n "$NAMESPACE" --type merge -p '{
  "data": {
    "mainContainer": "env:\n- name: OPENLINEAGE_NAMESPACE\n  valueFrom:\n    fieldRef:\n      fieldPath: metadata.namespace\n"
  }
}'

echo "Restarting workflow controller..."
oc rollout restart deployment/ds-pipeline-workflow-controller-dspa -n "$NAMESPACE"
oc rollout status deployment/ds-pipeline-workflow-controller-dspa -n "$NAMESPACE" --timeout=2m

echo "Done. All new KFP pipeline pods will have OPENLINEAGE_NAMESPACE set to their namespace."
