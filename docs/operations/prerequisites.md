# Prerequisites

Everything needed before deploying any component of this project.

**Last Updated:** 2026-05-28 (M5 complete — model serving + query stack added)

## Cluster Requirements

| Requirement | Specification | Notes |
|-------------|--------------|-------|
| OpenShift | 4.14+ | Required for RHOAI 3.4+ |
| RHOAI | 3.4+ | Provides KFP, model serving, workbench infrastructure. M1 verified on 3.4. vLLM `--task=embedding` requires 3.5+ (PG-018). |
| Cluster access | `cluster-admin` or namespace-scoped admin | For operator installation and CRD creation |
| CLI tools | `oc`, `helm`, `kubectl`, `kfp` | `oc` for OpenShift, `helm` for Milvus, `kfp` for pipeline compilation |

## GPU / Compute Resources

| Resource | Specification | Purpose | M1 Actual |
|----------|--------------|---------|-----------|
| GPU | 1x NVIDIA A100-80GB | Model serving — Hermes 70B FP8 via vLLM (M4/M5). 80GB VRAM required for FP8 quantized 70B model. | **Not needed for M1** — local sentence-transformers runs on CPU. GPU required from M4 (query path with vLLM). |
| CPU workers | 4 vCPU, 8GB RAM (per Ray worker) | RayData + Docling document processing | Verified: 2 workers × 4 CPU / 8GB processed 11 PDFs in ~4–5 min |
| Head node | 2 vCPU, 8GB RAM | Ray head node | Verified: default head config sufficient |
| Embedding (in-pod) | ~2 vCPU, 4GB RAM (within ingest_to_milvus pod) | Local Granite Embedding 125M (~500MB model download) | Verified: CPU embedding of 312 chunks completed in ~2 min |

## Operators

| Operator | Version | Purpose | Installation |
|----------|---------|---------|--------------|
| RHOAI Operator | 3.5+ | Platform foundation | OperatorHub |
| KubeRay Operator | 1.1+ | Ray cluster management | Installed via RHOAI |
| Milvus Operator | 2.4+ | Vector database (Certified Partner) | OperatorHub or Helm |
| MLflow Operator | Part of RHOAI 3.4+ | Experiment tracking | Installed via RHOAI DSC |
| GPU Operator | — | NVIDIA GPU support | OperatorHub |

## Storage

| Storage | Size | Purpose | Actual |
|---------|------|---------|--------|
| S3/MinIO (pipeline) | 5GB | Document staging, pipeline artifacts, JSONL chunks | 11 PDFs + JSONL output used <500MB. The Milvus Helm default creates a separate 500Gi MinIO (PG-017) — should be reduced. |
| PVC: `data-pvc` (RWX) | 5Gi | Shared document corpus (input PDFs) | Bound; 11 PDFs stored |
| PVC: `model-cache-pvc` (RWO) | 50Gi | Model weights cache (Mistral 7B for M4) | Bound; LLM weights cached but not needed for M1 ingest |
| Milvus storage | <1Gi | Vector storage for document corpus | 312 vectors (11 PDFs) is minimal; grows with corpus size |
| MariaDB (DSPA) | 10Gi | KFP pipeline metadata | Bound; used by DSPA for run history |
| PostgreSQL (Marquez) | 2Gi | Marquez lineage metadata store | M2: Deployed. Stores jobs, datasets, runs, facets. |
| MLflow (storage) | Managed by Operator | Experiment tracking backend | M2: Deployed cluster-wide by RHOAI MLflow Operator. No per-namespace PVC. |

## Network

| Requirement | Detail |
|-------------|--------|
| Egress | Access to `quay.io`, `registry.redhat.io`, `huggingface.co` for image pulls and model downloads |
| Internal DNS | Service discovery within namespace |
| Routes | OpenShift Routes for UI access (Chainlit, Registry, MLflow, Marquez) |

## External Dependencies

| Dependency | Purpose | How to Obtain |
|------------|---------|---------------|
| HuggingFace token | Gated model downloads (Granite embedding). Not required for Hermes 70B FP8 (ungated). | `huggingface.co/settings/tokens` |
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
