import { useEffect, useState } from 'react';
import {
  PageSection,
  Content,
  Card,
  CardBody,
  CardTitle,
  Form,
  FormGroup,
  TextInput,
  FormSelect,
  FormSelectOption,
  Button,
  Alert,
  Divider,
} from '@patternfly/react-core';
import { api, Collection } from '../api';

export function RegisterDocumentsPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [name, setName] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceSystem, setSourceSystem] = useState('manual');
  const [documentType, setDocumentType] = useState('');
  const [lineOfBusiness, setLineOfBusiness] = useState('');
  const [jurisdiction, setJurisdiction] = useState('');
  const [effectiveDate, setEffectiveDate] = useState('');
  const [targetCollection, setTargetCollection] = useState('');
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.listCollections().then((r) => {
      setCollections(r.collections);
      if (r.collections.length > 0) {
        setTargetCollection(r.collections[0].name);
      }
    });
  }, []);

  async function handleSubmit() {
    if (!name || !sourceUrl || !targetCollection) {
      setError('Name, Source URL, and Target Collection are required.');
      return;
    }

    setSubmitting(true);
    setError('');
    setSuccess('');

    try {
      const doc = await api.createDocument({
        name,
        source_url: sourceUrl,
        source_system: sourceSystem,
        document_type: documentType || 'unknown',
        line_of_business: lineOfBusiness || 'unknown',
        jurisdiction: jurisdiction || 'unknown',
        effective_date: effectiveDate || undefined,
        collections: [targetCollection],
      });

      setSuccess(`Document registered: ${doc.doc_id} — assigned to ${targetCollection}`);
      setName('');
      setSourceUrl('');
      setDocumentType('');
      setLineOfBusiness('');
      setJurisdiction('');
      setEffectiveDate('');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to register document');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PageSection>
      <Content component="h1">Register Documents</Content>
      <Content component="p">
        Add documents to the registry and assign them to a collection.
        The document gets a canonical doc_id and becomes trackable across
        ingest, query, and lineage.
      </Content>

      {success && <Alert variant="success" title={success} style={{ marginBottom: '1rem' }} />}
      {error && <Alert variant="danger" title={error} style={{ marginBottom: '1rem' }} />}

      <Card>
        <CardTitle>Document Identity</CardTitle>
        <CardBody>
          <Form isHorizontal>
            <FormGroup label="Document Name" isRequired fieldId="name">
              <TextInput
                id="name"
                value={name}
                onChange={(_e, val) => setName(val)}
                placeholder="e.g., GL Underwriting Guidelines 2026"
              />
            </FormGroup>
            <FormGroup label="Source URL" isRequired fieldId="source-url">
              <TextInput
                id="source-url"
                value={sourceUrl}
                onChange={(_e, val) => setSourceUrl(val)}
                placeholder="e.g., https://docs.internal/gl-guidelines-2026.pdf"
              />
            </FormGroup>
            <FormGroup label="Source System" fieldId="source-system">
              <FormSelect
                id="source-system"
                value={sourceSystem}
                onChange={(_e, val) => setSourceSystem(val)}
              >
                <FormSelectOption value="manual" label="Manual Upload" />
                <FormSelectOption value="s3" label="S3" />
                <FormSelectOption value="sharepoint" label="SharePoint" />
                <FormSelectOption value="internal" label="Internal" />
              </FormSelect>
            </FormGroup>
            <FormGroup label="Document Type" fieldId="document-type">
              <TextInput
                id="document-type"
                value={documentType}
                onChange={(_e, val) => setDocumentType(val)}
                placeholder="e.g., guideline, form, bulletin"
              />
            </FormGroup>
            <FormGroup label="Line of Business" fieldId="lob">
              <TextInput
                id="lob"
                value={lineOfBusiness}
                onChange={(_e, val) => setLineOfBusiness(val)}
                placeholder="e.g., general_liability, commercial_property"
              />
            </FormGroup>
            <FormGroup label="Jurisdiction" fieldId="jurisdiction">
              <TextInput
                id="jurisdiction"
                value={jurisdiction}
                onChange={(_e, val) => setJurisdiction(val)}
                placeholder="e.g., california, new_york, national"
              />
            </FormGroup>
            <FormGroup label="Effective Date" fieldId="effective-date">
              <TextInput
                id="effective-date"
                type="date"
                value={effectiveDate}
                onChange={(_e, val) => setEffectiveDate(val)}
              />
            </FormGroup>
          </Form>
        </CardBody>
      </Card>

      <Divider style={{ margin: '1rem 0' }} />

      <Card>
        <CardTitle>Collection Assignment</CardTitle>
        <CardBody>
          <Form isHorizontal>
            <FormGroup label="Target Collection" isRequired fieldId="collection">
              <FormSelect
                id="collection"
                value={targetCollection}
                onChange={(_e, val) => setTargetCollection(val)}
              >
                {collections.map((coll) => (
                  <FormSelectOption
                    key={coll.name}
                    value={coll.name}
                    label={`${coll.name} (${coll.document_count} docs)`}
                  />
                ))}
              </FormSelect>
            </FormGroup>
          </Form>

          <div style={{ marginTop: '1rem' }}>
            <Button
              variant="primary"
              onClick={handleSubmit}
              isDisabled={submitting || !name || !sourceUrl || !targetCollection}
              isLoading={submitting}
            >
              Register Document
            </Button>
          </div>
        </CardBody>
      </Card>
    </PageSection>
  );
}
