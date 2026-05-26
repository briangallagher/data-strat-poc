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

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
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
};
