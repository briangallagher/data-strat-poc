import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  PageSection,
  Content,
  TextInput,
  Button,
  Card,
  CardBody,
  CardTitle,
  Label,
  DescriptionList,
  DescriptionListGroup,
  DescriptionListTerm,
  DescriptionListDescription,
  Alert,
  Spinner,
  Divider,
  List,
  ListItem,
  Flex,
  FlexItem,
} from '@patternfly/react-core';
import { api, DocumentProvenance } from '../api';

export function ImpactAnalysisPage() {
  const [docId, setDocId] = useState('');
  const [provenance, setProvenance] = useState<DocumentProvenance | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [kfpBase, setKfpBase] = useState<{ dashboard: string; namespace: string } | null>(null);

  useEffect(() => {
    api.getExternalLinks()
      .then((links) => {
        if (links.kfp_dashboard && links.kfp_namespace) {
          setKfpBase({ dashboard: links.kfp_dashboard, namespace: links.kfp_namespace });
        }
      })
      .catch(() => {});
  }, []);

  async function handleSearch() {
    if (!docId.trim()) return;
    setLoading(true);
    setError('');
    setProvenance(null);

    try {
      const data = await api.getDocumentProvenance(docId.trim());
      setProvenance(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to fetch provenance');
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageSection>
      <Content component="h1">Impact Analysis</Content>
      <Content component="p">
        Enter a document ID to see its full impact: which collections contain it,
        which applications consume those collections, and which query traces cited it.
      </Content>

      <Flex>
        <FlexItem>
          <TextInput
            value={docId}
            onChange={(_e, val) => setDocId(val)}
            placeholder="Enter doc_id (e.g., ug-001)"
            aria-label="Document ID"
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            style={{ width: 300 }}
          />
        </FlexItem>
        <FlexItem>
          <Button
            variant="primary"
            onClick={handleSearch}
            isDisabled={!docId.trim() || loading}
          >
            Analyze Impact
          </Button>
        </FlexItem>
      </Flex>

      {loading && (
        <div style={{ marginTop: '2rem' }}>
          <Spinner size="lg" />
        </div>
      )}

      {error && (
        <Alert variant="danger" title={error} style={{ marginTop: '1rem' }} />
      )}

      {provenance && (
        <div style={{ marginTop: '2rem' }}>
          <Card>
            <CardTitle>
              <Link to={`/documents/${provenance.doc_id}`}>{provenance.doc_id}</Link>
              {' — '}
              {provenance.name}
            </CardTitle>
            <CardBody>
              <DescriptionList isHorizontal isCompact>
                <DescriptionListGroup>
                  <DescriptionListTerm>Source URL</DescriptionListTerm>
                  <DescriptionListDescription>
                    <a href={provenance.source_url} target="_blank" rel="noreferrer">
                      {provenance.source_url}
                    </a>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Collections</DescriptionListTerm>
                  <DescriptionListDescription>
                    {provenance.collections.map((coll) => (
                      <Link key={coll} to={`/collections/${coll}`} style={{ marginRight: 4 }}>
                        <Label color="blue" isCompact>{coll}</Label>
                      </Link>
                    ))}
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Pipeline Runs</DescriptionListTerm>
                  <DescriptionListDescription>
                    {provenance.pipeline_run_ids.length > 0 ? (
                      provenance.pipeline_run_ids.map((id) => (
                        kfpBase ? (
                          <a
                            key={id}
                            href={`${kfpBase.dashboard}/develop-train/pipelines/runs/${kfpBase.namespace}/runs/${id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ marginRight: 4 }}
                          >
                            <Label color="blue" isCompact>{id.slice(0, 8)}...</Label>
                          </a>
                        ) : (
                          <Label key={id} color="grey" isCompact style={{ marginRight: 4 }}>
                            {id.slice(0, 8)}...
                          </Label>
                        )
                      ))
                    ) : (
                      <span style={{ color: '#666' }}>None</span>
                    )}
                  </DescriptionListDescription>
                </DescriptionListGroup>
              </DescriptionList>

              <Divider style={{ margin: '1rem 0' }} />

              <Content component="h3">
                Query Traces Citing This Document ({provenance.recent_query_traces.length})
              </Content>

              {provenance.recent_query_traces.length === 0 ? (
                <Content component="p" style={{ color: '#666' }}>
                  No queries have cited this document yet.
                </Content>
              ) : (
                <List isPlain>
                  {provenance.recent_query_traces.map((trace) => (
                    <ListItem key={trace.trace_id}>
                      <Card isCompact style={{ marginBottom: 8 }}>
                        <CardBody>
                          <Link to={`/traces/${trace.trace_id}`}>
                            <strong>{trace.question || '(no question captured)'}</strong>
                          </Link>
                          <div style={{ marginTop: 4, fontSize: '0.85em', color: '#666' }}>
                            {trace.timestamp && new Date(parseInt(trace.timestamp)).toLocaleString()}
                            {' — '}
                            Collection: <Label color="blue" isCompact>{trace.collection}</Label>
                            {' — '}
                            {trace.chunks.length} chunks cited
                          </div>
                          {trace.answer_preview && (
                            <div style={{ marginTop: 4, fontSize: '0.85em' }}>
                              {trace.answer_preview.slice(0, 200)}...
                            </div>
                          )}
                        </CardBody>
                      </Card>
                    </ListItem>
                  ))}
                </List>
              )}

              {provenance.marquez_links.length > 0 && (
                <>
                  <Divider style={{ margin: '1rem 0' }} />
                  <Content component="h3">Marquez Lineage Links</Content>
                  <List isPlain>
                    {provenance.marquez_links.map((link, i) => (
                      <ListItem key={i}>
                        <a href={link.url} target="_blank" rel="noreferrer">
                          {link.job_name}
                        </a>
                        {link.run_id && (
                          <span style={{ color: '#666', marginLeft: 8 }}>
                            Run: {link.run_id.slice(0, 8)}...
                          </span>
                        )}
                      </ListItem>
                    ))}
                  </List>
                </>
              )}
            </CardBody>
          </Card>
        </div>
      )}
    </PageSection>
  );
}
