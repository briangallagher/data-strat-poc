import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  PageSection,
  Content,
  Card,
  CardBody,
  CardTitle,
  Grid,
  GridItem,
  DescriptionList,
  DescriptionListGroup,
  DescriptionListTerm,
  DescriptionListDescription,
  Label,
  LabelGroup,
  ExpandableSection,
  Spinner,
} from '@patternfly/react-core';
import { api } from '../api';

interface TraceDetail {
  info?: {
    request_id?: string;
    timestamp_ms?: number;
    status?: string;
    execution_time_ms?: number;
  };
  data?: {
    spans?: SpanDetail[];
    request?: string;
    response?: string;
  };
  tags?: Record<string, string>;
}

interface SpanDetail {
  name: string;
  span_type: string;
  status: { status_code: string };
  start_time_ns?: number;
  end_time_ns?: number;
  attributes?: Record<string, unknown>;
}

export function TraceDetailPage() {
  const { traceId } = useParams<{ traceId: string }>();
  const [trace, setTrace] = useState<TraceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!traceId) return;
    api.getTraceProvenance(traceId)
      .then((data) => setTrace(data as TraceDetail))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [traceId]);

  if (loading) return <PageSection><Spinner /></PageSection>;
  if (error) return <PageSection><Content>Error: {error}</Content></PageSection>;
  if (!trace) return <PageSection><Content>Trace not found</Content></PageSection>;

  const tags = trace.tags || {};
  const docIdsCited = (tags.doc_ids_cited || '').split(',').filter(Boolean);
  const pipelineRunIds = (tags.pipeline_run_ids || '').split(',').filter(Boolean);
  const spans = trace.data?.spans || [];

  return (
    <PageSection>
      <Content component="h1">Query Trace</Content>
      <Content component="p"><code>{traceId}</code></Content>

      <Grid hasGutter>
        <GridItem span={8}>
          <Card>
            <CardTitle>Question &amp; Answer</CardTitle>
            <CardBody>
              <DescriptionList>
                <DescriptionListGroup>
                  <DescriptionListTerm>Question</DescriptionListTerm>
                  <DescriptionListDescription>
                    <strong>{trace.data?.request || '-'}</strong>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Answer</DescriptionListTerm>
                  <DescriptionListDescription>
                    <div style={{ whiteSpace: 'pre-wrap' }}>
                      {trace.data?.response || '-'}
                    </div>
                  </DescriptionListDescription>
                </DescriptionListGroup>
              </DescriptionList>
            </CardBody>
          </Card>

          <Card style={{ marginTop: '1rem' }}>
            <CardTitle>Execution Spans ({spans.length})</CardTitle>
            <CardBody>
              {spans.map((span, i) => (
                <ExpandableSection
                  key={i}
                  toggleText={`${span.name} (${span.span_type}) — ${span.status.status_code}`}
                  isIndented
                >
                  <DescriptionList isCompact>
                    {span.attributes && Object.entries(span.attributes)
                      .filter(([k]) => !k.startsWith('mlflow.trace'))
                      .slice(0, 10)
                      .map(([k, v]) => (
                        <DescriptionListGroup key={k}>
                          <DescriptionListTerm>{k}</DescriptionListTerm>
                          <DescriptionListDescription>
                            <code style={{ fontSize: '0.85em', wordBreak: 'break-all' }}>
                              {JSON.stringify(v).slice(0, 300)}
                            </code>
                          </DescriptionListDescription>
                        </DescriptionListGroup>
                      ))}
                  </DescriptionList>
                </ExpandableSection>
              ))}
            </CardBody>
          </Card>
        </GridItem>

        <GridItem span={4}>
          <Card>
            <CardTitle>Provenance</CardTitle>
            <CardBody>
              <DescriptionList isCompact>
                <DescriptionListGroup>
                  <DescriptionListTerm>Collection</DescriptionListTerm>
                  <DescriptionListDescription>
                    <Label color="blue">
                      <Link to={`/collections/${tags.collection_queried}`}>
                        {tags.collection_queried || '-'}
                      </Link>
                    </Label>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Documents Cited</DescriptionListTerm>
                  <DescriptionListDescription>
                    <LabelGroup>
                      {docIdsCited.map((d) => (
                        <Label key={d} color="green">
                          <Link to={`/documents/${d}`}>{d}</Link>
                        </Label>
                      ))}
                      {docIdsCited.length === 0 && '-'}
                    </LabelGroup>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Chunks Retrieved</DescriptionListTerm>
                  <DescriptionListDescription>
                    {tags.chunks_retrieved_count || '-'}
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Pipeline Run IDs</DescriptionListTerm>
                  <DescriptionListDescription>
                    {pipelineRunIds.map((pid) => (
                      <div key={pid}><code>{pid.slice(0, 12)}...</code></div>
                    ))}
                    {pipelineRunIds.length === 0 && '-'}
                  </DescriptionListDescription>
                </DescriptionListGroup>
              </DescriptionList>
            </CardBody>
          </Card>

          <Card style={{ marginTop: '1rem' }}>
            <CardTitle>Trace Info</CardTitle>
            <CardBody>
              <DescriptionList isCompact>
                <DescriptionListGroup>
                  <DescriptionListTerm>Status</DescriptionListTerm>
                  <DescriptionListDescription>
                    <Label color={trace.info?.status === 'OK' ? 'green' : 'red'}>
                      {trace.info?.status || '-'}
                    </Label>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Duration</DescriptionListTerm>
                  <DescriptionListDescription>
                    {trace.info?.execution_time_ms ? `${trace.info.execution_time_ms}ms` : '-'}
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Timestamp</DescriptionListTerm>
                  <DescriptionListDescription>
                    {trace.info?.timestamp_ms
                      ? new Date(trace.info.timestamp_ms).toLocaleString()
                      : '-'}
                  </DescriptionListDescription>
                </DescriptionListGroup>
              </DescriptionList>
            </CardBody>
          </Card>
        </GridItem>
      </Grid>
    </PageSection>
  );
}
