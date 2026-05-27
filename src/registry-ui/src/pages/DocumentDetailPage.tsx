import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  PageSection,
  Content,
  DescriptionList,
  DescriptionListGroup,
  DescriptionListTerm,
  DescriptionListDescription,
  Label,
  LabelGroup,
  Card,
  CardBody,
  CardTitle,
  Grid,
  GridItem,
} from '@patternfly/react-core';
import { api, Document, LineageInfo } from '../api';

export function DocumentDetailPage() {
  const { docId } = useParams<{ docId: string }>();
  const [doc, setDoc] = useState<Document | null>(null);
  const [lineage, setLineage] = useState<LineageInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!docId) return;
    api.getDocument(docId).then(setDoc).catch((e) => setError(e.message));
    api.getDocumentLineage(docId).then(setLineage).catch(() => {});
  }, [docId]);

  if (error) return <PageSection><Content>Error: {error}</Content></PageSection>;
  if (!doc) return <PageSection><Content>Loading...</Content></PageSection>;

  return (
    <PageSection>
      <Content component="h1">
        {doc.doc_id}
        <Link to={`/documents/${doc.doc_id}/provenance`} style={{ marginLeft: '1rem', fontSize: '0.6em' }}>
          View Full Provenance →
        </Link>
      </Content>
      <Content component="p">{doc.name}</Content>

      <Grid hasGutter>
        <GridItem span={8}>
          <Card>
            <CardTitle>Document Metadata</CardTitle>
            <CardBody>
              <DescriptionList>
                <DescriptionListGroup>
                  <DescriptionListTerm>Doc ID</DescriptionListTerm>
                  <DescriptionListDescription><strong>{doc.doc_id}</strong></DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Status</DescriptionListTerm>
                  <DescriptionListDescription>
                    <Label color={doc.status === 'active' ? 'green' : 'orange'}>{doc.status}</Label>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Source System</DescriptionListTerm>
                  <DescriptionListDescription>{doc.source_system}</DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Source URL</DescriptionListTerm>
                  <DescriptionListDescription>
                    <a href={doc.source_url} target="_blank" rel="noopener noreferrer">{doc.source_url}</a>
                  </DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Document Type</DescriptionListTerm>
                  <DescriptionListDescription>{doc.document_type}</DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Line of Business</DescriptionListTerm>
                  <DescriptionListDescription>{doc.line_of_business}</DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Jurisdiction</DescriptionListTerm>
                  <DescriptionListDescription>{doc.jurisdiction}</DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Effective Date</DescriptionListTerm>
                  <DescriptionListDescription>{doc.effective_date || '-'}</DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Format</DescriptionListTerm>
                  <DescriptionListDescription>{doc.file_format || '-'}</DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Page Count</DescriptionListTerm>
                  <DescriptionListDescription>{doc.page_count || '-'}</DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>File Size</DescriptionListTerm>
                  <DescriptionListDescription>{doc.file_size_bytes ? `${(doc.file_size_bytes / 1024).toFixed(1)} KB` : '-'}</DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Content Hash</DescriptionListTerm>
                  <DescriptionListDescription><code>{doc.content_hash ? doc.content_hash.slice(0, 16) + '...' : '-'}</code></DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Collections</DescriptionListTerm>
                  <DescriptionListDescription>
                    <LabelGroup>
                      {doc.collections.map((c) => (
                        <Label key={c} color="blue"><Link to={`/collections/${c}`}>{c}</Link></Label>
                      ))}
                    </LabelGroup>
                  </DescriptionListDescription>
                </DescriptionListGroup>
              </DescriptionList>
            </CardBody>
          </Card>
        </GridItem>

        <GridItem span={4}>
          <Card>
            <CardTitle>OpenLineage Identity</CardTitle>
            <CardBody>
              <DescriptionList isCompact>
                <DescriptionListGroup>
                  <DescriptionListTerm>Namespace</DescriptionListTerm>
                  <DescriptionListDescription><code>{doc.ol_namespace}</code></DescriptionListDescription>
                </DescriptionListGroup>
                <DescriptionListGroup>
                  <DescriptionListTerm>Name</DescriptionListTerm>
                  <DescriptionListDescription><code>{doc.ol_name}</code></DescriptionListDescription>
                </DescriptionListGroup>
              </DescriptionList>
            </CardBody>
          </Card>

          {lineage && lineage.ingested_by.length > 0 && (
            <Card style={{ marginTop: '1rem' }}>
              <CardTitle>Lineage</CardTitle>
              <CardBody>
                <Content component="h4">Ingested By</Content>
                {lineage.ingested_by.map((entry, i) => (
                  <DescriptionList key={i} isCompact style={{ marginBottom: '0.5rem' }}>
                    <DescriptionListGroup>
                      <DescriptionListTerm>Pipeline Run</DescriptionListTerm>
                      <DescriptionListDescription><code>{(entry as Record<string, string>).pipeline_run_id?.slice(0, 8)}...</code></DescriptionListDescription>
                    </DescriptionListGroup>
                    <DescriptionListGroup>
                      <DescriptionListTerm>Collection</DescriptionListTerm>
                      <DescriptionListDescription>{(entry as Record<string, string>).collection}</DescriptionListDescription>
                    </DescriptionListGroup>
                  </DescriptionList>
                ))}
              </CardBody>
            </Card>
          )}
        </GridItem>
      </Grid>
    </PageSection>
  );
}
