const BASE = '/api/v1';

export interface Document {
  id: string;
  doc_id: string;
  name: string;
  source_system: string;
  source_url: string;
  document_type: string;
  line_of_business: string;
  jurisdiction: string;
  effective_date: string | null;
  status: string;
  ol_namespace: string;
  ol_name: string;
  content_hash: string | null;
  file_format: string | null;
  page_count: number | null;
  file_size_bytes: number | null;
  collections: string[];
  created_at: string;
  updated_at: string;
}

export interface CollectionMember {
  doc_id: string;
  name: string;
  document_type: string;
  status: string;
  added_at: string;
  added_by: string;
  last_ingested: string | null;
  last_pipeline_run: string | null;
  vector_count: number | null;
}

export interface Collection {
  id: string;
  name: string;
  description: string | null;
  doc_id_prefix: string;
  next_sequence: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  document_count: number;
  members?: CollectionMember[];
}

export interface LineageInfo {
  doc_id: string;
  ol_namespace: string;
  ol_name: string;
  ingested_by: Record<string, unknown>[];
  consumed_by: Record<string, unknown>[];
}

export interface TraceChunk {
  doc_id: string;
  chunk_index: number;
  pipeline_run_id: string;
  text_preview: string;
  score: number;
}

export interface TraceSummary {
  trace_id: string;
  timestamp: string;
  question: string;
  answer_preview: string;
  collection: string;
  chunks: TraceChunk[];
  doc_ids_cited: string[];
}

export interface MarquezLink {
  job_name: string;
  run_id: string;
  namespace: string;
  url: string;
}

export interface DocumentProvenance {
  doc_id: string;
  name: string;
  source_url: string;
  collections: string[];
  pipeline_run_ids: string[];
  marquez_links: MarquezLink[];
  recent_query_traces: TraceSummary[];
}

export interface CollectionProvenance {
  collection_name: string;
  document_count: number;
  downstream_apps: string[];
  query_count: number;
  marquez_jobs: MarquezLink[];
}

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export interface CollectionHealth {
  collection_name: string;
  document_count: number;
  vector_count: number;
  consuming_apps: string[];
  query_count: number;
  last_ingest: string | null;
  staleness_days: number | null;
  marquez_jobs: MarquezLink[];
}

export interface AppInfo {
  app_name: string;
  collections: string[];
  query_count: number;
  last_query: string | null;
  workflow_type: string;
}

export const api = {
  listDocuments(params?: { collection?: string; status?: string }): Promise<{ documents: Document[]; total: number }> {
    const sp = new URLSearchParams();
    if (params?.collection) sp.set('collection', params.collection);
    if (params?.status) sp.set('status', params.status);
    return fetchJSON(`${BASE}/documents?${sp.toString()}`);
  },

  getDocument(docId: string): Promise<Document> {
    return fetchJSON(`${BASE}/documents/${docId}`);
  },

  getDocumentLineage(docId: string): Promise<LineageInfo> {
    return fetchJSON(`${BASE}/documents/${docId}/lineage`);
  },

  listCollections(): Promise<{ collections: Collection[]; total: number }> {
    return fetchJSON(`${BASE}/collections`);
  },

  getCollection(name: string): Promise<Collection> {
    return fetchJSON(`${BASE}/collections/${name}`);
  },

  createCollection(data: { name: string; description?: string; doc_id_prefix: string }): Promise<Collection> {
    return fetchJSON(`${BASE}/collections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  assignToCollection(collectionName: string, docIds: string[]): Promise<{ assigned: number }> {
    return fetchJSON(`${BASE}/collections/${collectionName}/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_ids: docIds }),
    });
  },

  removeFromCollection(collectionName: string, docId: string): Promise<{ removed: string }> {
    return fetchJSON(`${BASE}/collections/${collectionName}/documents/${docId}`, {
      method: 'DELETE',
    });
  },

  getDocumentProvenance(docId: string): Promise<DocumentProvenance> {
    return fetchJSON(`${BASE}/provenance/document/${docId}`);
  },

  listTraces(): Promise<{ traces: TraceSummary[]; total: number }> {
    return fetchJSON(`${BASE}/provenance/traces`);
  },

  getTraceProvenance(traceId: string): Promise<Record<string, unknown>> {
    return fetchJSON(`${BASE}/provenance/trace/${traceId}`);
  },

  getCollectionProvenance(collectionName: string): Promise<CollectionProvenance> {
    return fetchJSON(`${BASE}/provenance/collection/${collectionName}`);
  },

  getCollectionHealth(collectionName: string): Promise<CollectionHealth> {
    return fetchJSON(`${BASE}/provenance/collection/${collectionName}/health`);
  },

  listApps(): Promise<AppInfo[]> {
    return fetchJSON(`${BASE}/provenance/apps`);
  },

  createDocument(data: {
    name: string;
    source_url: string;
    source_system: string;
    document_type: string;
    line_of_business: string;
    jurisdiction: string;
    effective_date?: string;
    collections: string[];
  }): Promise<Document> {
    return fetchJSON(`${BASE}/documents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },
};
