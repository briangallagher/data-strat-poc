# Prerequisites

Everything needed before deploying any component of this project.

**Last Updated:** 2026-05-22 (M0 — initial draft, concrete specs to be filled during M0 execution)

## Cluster Requirements

| Requirement | Specification | Notes |
|-------------|--------------|-------|
| OpenShift | 4.14+ | Required for RHOAI 3.5+ |
| RHOAI | 3.5+ | Provides KFP, model serving, workbench infrastructure |
| Cluster access | `cluster-admin` or namespace-scoped admin | For operator installation and CRD creation |
| CLI tools | `oc`, `helm`, `kubectl`, `kfp` | `oc` for OpenShift, `helm` for Milvus, `kfp` for pipeline compilation |

## GPU / Compute Resources

| Resource | Specification | Purpose |
|----------|--------------|---------|
| GPU | 1x NVIDIA L40S, A100, or H100 (minimum 24GB VRAM) | Model serving (embedding + LLM inference) |
| CPU workers | 4+ vCPU, 16GB RAM (per Ray worker) | RayData + Docling document processing |
| Head node | 2 vCPU, 8GB RAM | Ray head node |

<!-- TODO: Refine based on M1 actual measurements -->

## Operators

| Operator | Version | Purpose | Installation |
|----------|---------|---------|--------------|
| RHOAI Operator | 3.5+ | Platform foundation | OperatorHub |
| KubeRay Operator | 1.1+ | Ray cluster management | Installed via RHOAI |
| Milvus Operator | 2.4+ | Vector database (Certified Partner) | OperatorHub or Helm |
| GPU Operator | — | NVIDIA GPU support | OperatorHub |

## Storage

| Storage | Size | Purpose |
|---------|------|---------|
| S3/MinIO | 10GB+ | Document staging, pipeline artifacts, model cache |
| PVC (RWX) | 5GB+ | Shared document corpus |
| PVC (RWO) | 20GB+ | Model weights cache |
| PostgreSQL | 5GB | Marquez backend, MLflow backend |

<!-- TODO: Refine storage sizes based on M1 corpus measurements -->

## Network

| Requirement | Detail |
|-------------|--------|
| Egress | Access to `quay.io`, `registry.redhat.io`, `huggingface.co` for image pulls and model downloads |
| Internal DNS | Service discovery within namespace |
| Routes | OpenShift Routes for UI access (Gradio, MLflow, Marquez) |

## External Dependencies

| Dependency | Purpose | How to Obtain |
|------------|---------|---------------|
| HuggingFace token | Gated model downloads (Granite, Mistral) | `huggingface.co/settings/tokens` |
| Document corpus | Test PDFs for ingest pipeline | Downloaded via `download-corpus.sh` or supplied manually |

## Development Environment

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Pipeline components, scripts |
| `kfp` | 2.x | Pipeline compilation |
| `oc` | 4.14+ | Cluster interaction |
| `helm` | 3.x | Milvus deployment |

## Verification

Run these checks to confirm prerequisites are met:

```bash
# OpenShift access
oc whoami
oc version

# RHOAI installed
oc get dsci -A

# GPU available
oc get nodes -l nvidia.com/gpu.present=true

# Operators
oc get csv -n redhat-ods-operator | grep rhods
oc get csv -A | grep kuberay
```
