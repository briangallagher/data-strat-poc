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
  EmptyState,
  EmptyStateBody,
  Spinner,
} from '@patternfly/react-core';
import { Table, Thead, Tr, Th, Tbody, Td } from '@patternfly/react-table';
import { api, DocumentProvenance } from '../api';

export function DocumentProvenancePage() {
  const { docId } = useParams<{ docId: string }>();
  const [prov, setProv] = useState<DocumentProvenance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!docId) return;
    api.getDocumentProvenance(docId)
      .then(setProv)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [docId]);

  if (loading) return <PageSection><Spinner /></PageSection>;
  if (error) return <PageSection><Content>Error: {error}</Content></PageSection>;
  if (!prov) return <PageSection><Content>Document not found</Content></PageSection>;

  return (
    <PageSection>
      <Content component="h1">Provenance: {prov.doc_id}</Content>
      <Content component="p">
        Full provenance for <strong>{prov.name}</strong> — collections, ingest pipeline runs,
        query traces that cited this document, and links to Marquez lineage.
      </Content>

      <Grid hasGutter>
        <GridItem span={6}>
          <Card>
            <CardTitle>Document Identity</CardTitle>
            <CardBody>
              <DescriptionList isCompact>
                <DescriptionListGroup>
                  <DescriptionListTerm>Doc ID</DescriptionListTerm>
                  <DescriptionListDescription>
                    <Link to={`/documents/${prov.doc_id}`}><strong>{prov.doc_id}</strong></Link>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Name</DescriptionListTerm>
                  <DescriptionListDescription>{prov.name}</DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Source URL</DescriptionListTerm>
                  <DescriptionListDescription>
                    <a href={prov.source_url} target="_blank" rel="noopener noreferrer">
                      {prov.source_url}
                    </a>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Collections</DescriptionListTerm>
                  <DescriptionListDescription>
                    <LabelGroup>
                      {prov.collections.map((c) => (
                        <Label key={c} color="blue">
                          <Link to={`/collections/${c}`}>{c}</Link>
                        </Label>
                      ))}
                    </LabelGroup>
                  </DescriptionListDescription>
                </DescriptionListGroup>
              </DescriptionList>
            </CardBody>
          </Card>

          <Card style={{ marginTop: '1rem' }}>
            <CardTitle>Ingest Pipeline Runs</CardTitle>
            <CardBody>
              {prov.pipeline_run_ids.length > 0 ? (
                <DescriptionList isCompact>
                  {prov.pipeline_run_ids.map((pid) => (
                    <DescriptionListGroup key={pid}>
                      <DescriptionListTerm>pipeline_run_id</DescriptionListTerm>
                      <DescriptionListDescription><code>{pid}</code></DescriptionListDescription>
                    </DescriptionListGroup>
                  ))}
                </DescriptionList>
              ) : (
                <Content>No pipeline runs recorded.</Content>
              )}
            </CardBody>
          </Card>

          {prov.marquez_links.length > 0 && (
            <Card style={{ marginTop: '1rem' }}>
              <CardTitle>Marquez Lineage</CardTitle>
              <CardBody>
                {prov.marquez_links.map((link, i) => (
                  <DescriptionList key={i} isCompact style={{ marginBottom: '0.5rem' }}>
                    <DescriptionListGroup>
                      <DescriptionListTerm>Job</DescriptionListTerm>
                      <DescriptionListDescription>
                        <a href={link.url} target="_blank" rel="noopener noreferrer">{link.job_name}</a>
                      </DescriptionListDescription>
                    </DescriptionListGroup>
                  </DescriptionList>
                ))}
              </CardBody>
            </Card>
          )}
        </GridItem>

        <GridItem span={6}>
          <Card>
            <CardTitle>Query Traces Citing This Document</CardTitle>
            <CardBody>
              {prov.recent_query_traces.length > 0 ? (
                <Table variant="compact">
                  <Thead>
                    <Tr>
                      <Th>Trace</Th>
                      <Th>Question</Th>
                      <Th>Collection</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {prov.recent_query_traces.map((t) => (
                      <Tr key={t.trace_id}>
                        <Td>
                          <Link to={`/traces/${t.trace_id}`}>
                            <code>{t.trace_id.slice(0, 12)}...</code>
                          </Link>
                        </Td>
                        <Td>{t.question.slice(0, 60)}{t.question.length > 60 ? '...' : ''}</Td>
                        <Td><Label color="blue">{t.collection || '-'}</Label></Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              ) : (
                <EmptyState>
                  <EmptyStateBody>
                    No queries have cited this document yet.
                  </EmptyStateBody>
                </EmptyState>
              )}
            </CardBody>
          </Card>
        </GridItem>
      </Grid>
    </PageSection>
  );
}
