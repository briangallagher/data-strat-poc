import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  PageSection,
  Content,
  Card,
  CardBody,
  Label,
  LabelGroup,
  EmptyState,
  EmptyStateBody,
  Spinner,
} from '@patternfly/react-core';
import { Table, Thead, Tr, Th, Tbody, Td } from '@patternfly/react-table';
import { api, TraceSummary } from '../api';

export function QueryTracesPage() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getDocumentProvenance('ug-001')
      .then((prov) => setTraces(prov.recent_query_traces))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <PageSection><Spinner /></PageSection>;
  if (error) return <PageSection><Content>Error: {error}</Content></PageSection>;

  return (
    <PageSection>
      <Content component="h1">Query Traces</Content>
      <Content component="p">
        Recent queries answered by the underwriting knowledge assistant.
        Each trace captures the full provenance chain: question → retrieved chunks → source documents.
      </Content>

      {traces.length === 0 ? (
        <EmptyState>
          <EmptyStateBody>
            No query traces yet. Ask a question via the Chainlit chat interface to generate traces.
          </EmptyStateBody>
        </EmptyState>
      ) : (
        <Card>
          <CardBody>
            <Table variant="compact">
              <Thead>
                <Tr>
                  <Th>Trace ID</Th>
                  <Th>Timestamp</Th>
                  <Th>Question</Th>
                  <Th>Collection</Th>
                  <Th>Documents Cited</Th>
                </Tr>
              </Thead>
              <Tbody>
                {traces.map((t) => (
                  <Tr key={t.trace_id}>
                    <Td>
                      <Link to={`/traces/${t.trace_id}`}>
                        <code>{t.trace_id.slice(0, 16)}...</code>
                      </Link>
                    </Td>
                    <Td>{new Date(Number(t.timestamp)).toLocaleString()}</Td>
                    <Td>{t.question.slice(0, 80)}{t.question.length > 80 ? '...' : ''}</Td>
                    <Td><Label color="blue">{t.collection || '-'}</Label></Td>
                    <Td>
                      <LabelGroup>
                        {t.doc_ids_cited.map((d) => (
                          <Label key={d} color="green">
                            <Link to={`/documents/${d}`}>{d}</Link>
                          </Label>
                        ))}
                      </LabelGroup>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </CardBody>
        </Card>
      )}
    </PageSection>
  );
}
