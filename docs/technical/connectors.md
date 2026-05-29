# Connector Architecture

## What This Is

Connectors are pluggable source-system adapters that authenticate with external systems and fetch documents to a local staging area. They have no knowledge of collections, Milvus, or routing — they are pure data access components used by both the ingest pipeline (M3) and the future discovery workflow (PG-033).

## Connector ABC

All connectors implement a three-method abstract base class:

```python
class Connector(ABC):
    @abstractmethod
    def authenticate(self, credentials: dict) -> None:
        """Establish authenticated session with source system."""

    @abstractmethod
    def resolve(self, source_config: dict) -> list[SourceDocument]:
        """Scan source system and return all available documents.
        Used by discovery workflow only (PG-033). NOT called during ingest."""

    @abstractmethod
    def fetch_to_staging(self, source_url: str, staging_path: str) -> Path:
        """Download a single document from source to local staging area."""
```

| Method | Used In | Purpose |
|--------|---------|---------|
| `authenticate` | Ingest + Discovery | Establish credentials (S3 keys, OAuth tokens, API keys) |
| `resolve` | Discovery only (PG-033) | Scan source, list what's available. NOT used in ingest (ADR-010) |
| `fetch_to_staging` | Ingest | Download one document to S3 staging |

The interface is intentionally kept unified (all 3 methods in one ABC) even though `resolve` is unused in M3. Splitting into Fetcher/Discoverer interfaces is deferred to PG-035 once the discovery workflow proves the boundary.

## S3Connector

The primary connector for the POC. Works against the cluster MinIO instance.

**How it works:**

1. `authenticate` — reads S3 credentials from a Kubernetes Secret (access key + secret key + endpoint URL)
2. `resolve` — lists all objects under a configured bucket prefix, returns `SourceDocument` with key, size, last modified
3. `fetch_to_staging` — copies an object from the corpus bucket to the staging prefix in the same MinIO instance

```python
connector = S3Connector()
connector.authenticate({
    "endpoint_url": "http://minio-service:9000",
    "access_key": "...",
    "secret_key": "...",
    "bucket": "corpus"
})

path = connector.fetch_to_staging(
    source_url="s3://corpus/underwriting_guidelines/ca-doi-2025-3.pdf",
    staging_path="s3://staging/run-abc/ca-doi-2025-3.pdf"
)
```

In the POC, source and staging are both on the same MinIO instance. In production, the source would be an external S3 bucket or object store, and staging would be a pipeline-local area.

## Confluence Mock

**Status:** Stretch goal. Code exists from the prior POC but was not exercised in M3.

The mock connector simulates Confluence page retrieval by reading pre-staged HTML files from a local directory. It demonstrates the connector interface without requiring a live Confluence instance. If ported, it would use the same `authenticate`/`fetch_to_staging` pattern with Confluence REST API credentials.

## How acquire_documents Uses Connectors

The `acquire_documents` KFP component orchestrates connectors but does NOT scan sources:

```
1. Query registry:  GET /documents?collection=X&status=active
                    → list of (doc_id, source_url, metadata)

2. Authenticate:    connector.authenticate(credentials_from_secret)

3. For each doc:    connector.fetch_to_staging(source_url, staging_path)
                    If 404 → skip, flag status=unavailable in registry

4. Write manifest:  manifest.json with per-doc metadata to S3 staging

5. Emit lineage:    Per-doc OL InputDataset events (ADR-011)

6. Log to MLflow:   Document count, bytes fetched, connector type
```

The registry is authoritative (ADR-010): `acquire_documents` fetches only what the registry explicitly lists. Unknown files in the source system are ignored — that's the discovery workflow's job.

## Adding a New Connector

1. Implement the `Connector` ABC (all 3 methods)
2. Register the connector type in `acquire_documents` component params (e.g., `connector_type="confluence"`)
3. Create a Kubernetes Secret with the connector's credentials
4. Add the connector type to `config/collections.yaml` for the relevant collection

No routing logic is needed in the connector. The registry handles document-to-collection assignment. The connector just fetches what it's told to fetch.

## Relationship to Discovery Workflow

The discovery workflow (PG-033, not built in M3) will use `connector.resolve()` to scan source systems:

```
Discovery:   connector.resolve()  → "here's what the source has"
             compare with registry → register new, flag missing, detect changes

Ingest:      registry.list()      → "here's what to process"
             connector.fetch()    → download to staging
```

These are intentionally separate workflows (ADR-012). The ingest pipeline never discovers — it trusts the registry. The discovery workflow never processes — it updates the registry. The connector ABC serves both, but each workflow uses different methods.

## Design Decisions

- **ADR-008:** Connector ABC pattern — keep unified interface, defer split
- **ADR-010:** Registry authoritative for ingest — connectors don't scan during ingest
- **ADR-012:** Three-concern architecture — connecting is a capability, not a workflow

## References

| Source | Link |
|--------|------|
| Connector code | `src/registry/connectors/` |
| acquire_documents | `pipelines-components` fork (branch `data-strat-poc`) |
| Collections config | `config/collections.yaml` |
| M3 Plan | `docs/milestones/M3-connectors/plan.md` |
