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
  Popover,
  Icon,
} from '@patternfly/react-core';
import { OutlinedQuestionCircleIcon } from '@patternfly/react-icons';
import { Table, Thead, Tr, Th, Tbody, Td } from '@patternfly/react-table';
import { api } from '../api';

interface ChunkDetail {
  doc_id: string;
  chunk_index: number;
  pipeline_run_id: string;
  score: number;
  text_preview: string;
  section_path: string;
  page_numbers: string;
}

interface TraceProvenance {
  trace_id: string;
  timestamp: string;
  status: string;
  execution_time_ms: number | null;
  question: string;
  answer_preview: string;
  collection: string;
  doc_ids_cited: string[];
  chunks: ChunkDetail[];
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

          {trace.chunks && trace.chunks.length > 0 && (
            <Card style={{ marginTop: '1rem' }}>
              <CardTitle>Document Sections ({trace.chunks.length})</CardTitle>
              <CardBody>
                <Table variant="compact">
                  <Thead>
                    <Tr>
                      <Th>Document</Th>
                      <Th>Page</Th>
                      <Th>Section</Th>
                      <Th>Relevance</Th>
                      <Th>
                        Parsed Text{' '}
                        <Popover
                          headerContent="What is this text?"
                          bodyContent={
                            <div>
                              <p>This is the text that was fed to the AI model as context for generating the answer. It is <strong>not</strong> a verbatim excerpt from the original PDF.</p>
                              <p style={{ marginTop: '0.5rem' }}>Documents are processed by <strong>Docling</strong>, which detects layout (columns, tables, headers) and reconstructs the text in a logical reading order. This means the text may read differently from what you see when you open the PDF, especially for multi-column layouts, tables, and cross-references.</p>
                              <p style={{ marginTop: '0.5rem' }}>Use the <strong>Page</strong> and <strong>Section</strong> columns to locate the original passage in the source document.</p>
                            </div>
                          }
                        >
                          <Icon size="sm" style={{ cursor: 'pointer', marginLeft: '0.25rem' }}>
                            <OutlinedQuestionCircleIcon />
                          </Icon>
                        </Popover>
                      </Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {trace.chunks.map((chunk, i) => (
                      <Tr key={i}>
                        <Td>
                          <Link to={`/documents/${chunk.doc_id}`}>
                            <strong>{chunk.doc_id}</strong>
                          </Link>
                        </Td>
                        <Td>{chunk.page_numbers || '-'}</Td>
                        <Td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {chunk.section_path || '-'}
                        </Td>
                        <Td>{chunk.score.toFixed(4)}</Td>
                        <Td style={{ maxWidth: '350px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.85em', color: '#6a6e73' }}>
                          {chunk.text_preview}
                        </Td>
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
            <CardTitle>MLflow Trace</CardTitle>
            <CardBody>
              <DescriptionList isCompact>
                <DescriptionListGroup>
                  <DescriptionListTerm>Trace ID</DescriptionListTerm>
                  <DescriptionListDescription>
                    <code style={{ fontSize: '0.8em' }}>{trace.trace_id}</code>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>View in MLflow</DescriptionListTerm>
                  <DescriptionListDescription>
                    <a href={trace.mlflow_url} target="_blank" rel="noopener noreferrer">
                      Open in RHOAI MLflow →
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
