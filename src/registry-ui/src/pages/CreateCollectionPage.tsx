import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PageSection,
  Content,
  Card,
  CardBody,
  CardTitle,
  Form,
  FormGroup,
  FormHelperText,
  HelperText,
  HelperTextItem,
  TextInput,
  TextArea,
  Button,
  ActionGroup,
  Alert,
} from '@patternfly/react-core';
import { api } from '../api';

export function CreateCollectionPage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [prefix, setPrefix] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!name || !prefix) {
      setError('Name and doc_id prefix are required');
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await api.createCollection({ name, description: description || undefined, doc_id_prefix: prefix });
      navigate(`/collections/${name}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create collection');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageSection>
      <Content component="h1">Create Collection</Content>
      <Content component="p">
        Define a new logical grouping of documents. The collection name will also be the Milvus collection name.
      </Content>

      <Card style={{ maxWidth: '600px' }}>
        <CardTitle>New Collection</CardTitle>
        <CardBody>
          {error && <Alert variant="danger" title={error} style={{ marginBottom: '1rem' }} />}

          <Form>
            <FormGroup label="Collection Name" isRequired fieldId="name">
              <TextInput
                id="name"
                value={name}
                onChange={(_e, v) => setName(v)}
                placeholder="e.g., underwriting_guidelines"
                isRequired
              />
              <FormHelperText>
                <HelperText><HelperTextItem>Must be lowercase with underscores (e.g., underwriting_guidelines)</HelperTextItem></HelperText>
              </FormHelperText>
            </FormGroup>

            <FormGroup label="Description" fieldId="description">
              <TextArea
                id="description"
                value={description}
                onChange={(_e, v) => setDescription(v)}
                placeholder="What documents belong in this collection?"
              />
            </FormGroup>

            <FormGroup label="Doc ID Prefix" isRequired fieldId="prefix">
              <TextInput
                id="prefix"
                value={prefix}
                onChange={(_e, v) => setPrefix(v)}
                placeholder="e.g., ug"
                isRequired
              />
              <FormHelperText>
                <HelperText><HelperTextItem>2-3 character prefix for auto-generated doc_ids (e.g., ug, rb, if)</HelperTextItem></HelperText>
              </FormHelperText>
            </FormGroup>

            <ActionGroup>
              <Button variant="primary" onClick={handleSubmit} isLoading={isSubmitting} isDisabled={isSubmitting}>
                Create Collection
              </Button>
              <Button variant="link" onClick={() => navigate('/collections')}>
                Cancel
              </Button>
            </ActionGroup>
          </Form>
        </CardBody>
      </Card>
    </PageSection>
  );
}
