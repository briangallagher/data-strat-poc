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
  Spinner,
} from '@patternfly/react-core';
import { Table, Thead, Tr, Th, Tbody, Td } from '@patternfly/react-table';
import { api } from '../api';

interface TraceProvenance {
  trace_id: string;
  timestamp: string;
  status: string;
  execution_time_ms: number | null;
  question: string;
  answer_preview: string;
  collection: string;
  doc_ids_cited: string[];
  documents: {
    doc_id: string;
    name: string;
    source_url: string;
    document_type: string;
    line_of_business: string;
    jurisdiction: string;
  }[];
  mlflow_url: string;
}

export function TraceDetailPage() {
  const { traceId } = useParams<{ traceId: string }>();
  const [trace, setTrace] = useState<TraceProvenance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!traceId) return;
    api.getTraceProvenance(traceId)
      .then((data) => setTrace(data as unknown as TraceProvenance))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [traceId]);

  if (loading) return <PageSection><Spinner /></PageSection>;
  if (error) return <PageSection><Content>Error: {error}</Content></PageSection>;
  if (!trace) return <PageSection><Content>Trace not found</Content></PageSection>;

  return (
    <PageSection>
      <Content component="h1">Query Trace</Content>
      <Content component="p"><code>{trace.trace_id}</code></Content>

      <Grid hasGutter>
        <GridItem span={8}>
          <Card>
            <CardTitle>Question &amp; Answer</CardTitle>
            <CardBody>
              <DescriptionList>
                <DescriptionListGroup>
                  <DescriptionListTerm>Question</DescriptionListTerm>
                  <DescriptionListDescription>
                    <strong>{trace.question || '-'}</strong>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Answer</DescriptionListTerm>
                  <DescriptionListDescription>
                    <div style={{ whiteSpace: 'pre-wrap' }}>
                      {trace.answer_preview || 'Answer not captured in trace metadata'}
                    </div>
                  </DescriptionListDescription>
                </DescriptionListGroup>
              </DescriptionList>
            </CardBody>
          </Card>

          {trace.documents.length > 0 && (
            <Card style={{ marginTop: '1rem' }}>
              <CardTitle>Source Documents</CardTitle>
              <CardBody>
                <Table variant="compact">
                  <Thead>
                    <Tr>
                      <Th>Doc ID</Th>
                      <Th>Name</Th>
                      <Th>Type</Th>
                      <Th>LOB</Th>
                      <Th>Jurisdiction</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {trace.documents.map((doc) => (
                      <Tr key={doc.doc_id}>
                        <Td>
                          <Link to={`/documents/${doc.doc_id}`}>
                            <strong>{doc.doc_id}</strong>
                          </Link>
                        </Td>
                        <Td>{doc.name}</Td>
                        <Td><Label>{doc.document_type}</Label></Td>
                        <Td>{doc.line_of_business}</Td>
                        <Td>{doc.jurisdiction}</Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </CardBody>
            </Card>
          )}
        </GridItem>

        <GridItem span={4}>
          <Card>
            <CardTitle>Trace Info</CardTitle>
            <CardBody>
              <DescriptionList isCompact>
                <DescriptionListGroup>
                  <DescriptionListTerm>Status</DescriptionListTerm>
                  <DescriptionListDescription>
                    <Label color={trace.status === 'OK' ? 'green' : 'red'}>
                      {trace.status || '-'}
                    </Label>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Duration</DescriptionListTerm>
                  <DescriptionListDescription>
                    {trace.execution_time_ms ? `${(trace.execution_time_ms / 1000).toFixed(1)}s` : '-'}
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Timestamp</DescriptionListTerm>
                  <DescriptionListDescription>
                    {trace.timestamp
                      ? new Date(Number(trace.timestamp)).toLocaleString()
                      : '-'}
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Collection</DescriptionListTerm>
                  <DescriptionListDescription>
                    {trace.collection ? (
                      <Label color="blue">
                        <Link to={`/collections/${trace.collection}`}>{trace.collection}</Link>
                      </Label>
                    ) : '-'}
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Documents Cited</DescriptionListTerm>
                  <DescriptionListDescription>
                    <LabelGroup>
                      {trace.doc_ids_cited.map((d) => (
                        <Label key={d} color="green">
                          <Link to={`/documents/${d}`}>{d}</Link>
                        </Label>
                      ))}
                      {trace.doc_ids_cited.length === 0 && '-'}
                    </LabelGroup>
                  </DescriptionListDescription>
                </DescriptionListGroup>
              </DescriptionList>
            </CardBody>
          </Card>

          <Card style={{ marginTop: '1rem' }}>
            <CardTitle>External Links</CardTitle>
            <CardBody>
              <DescriptionList isCompact>
                <DescriptionListGroup>
                  <DescriptionListTerm>MLflow Trace</DescriptionListTerm>
                  <DescriptionListDescription>
                    <a href={trace.mlflow_url} target="_blank" rel="noopener noreferrer">
                      View in MLflow UI →
                    </a>
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
