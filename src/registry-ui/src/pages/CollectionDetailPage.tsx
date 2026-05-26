import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  PageSection,
  Content,
  Card,
  CardBody,
  CardTitle,
  DescriptionList,
  DescriptionListGroup,
  DescriptionListTerm,
  DescriptionListDescription,
  Button,
  Modal,
  ModalVariant,
  Label,
} from '@patternfly/react-core';
import { Table, Thead, Tr, Th, Tbody, Td } from '@patternfly/react-table';
import { api, Collection, Document } from '../api';

export function CollectionDetailPage() {
  const { name } = useParams<{ name: string }>();
  const [collection, setCollection] = useState<Collection | null>(null);
  const [allDocs, setAllDocs] = useState<Document[]>([]);
  const [isAssignOpen, setIsAssignOpen] = useState(false);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);

  const load = () => {
    if (!name) return;
    api.getCollection(name).then(setCollection);
  };

  useEffect(() => {
    load();
    api.listDocuments({ status: 'active' }).then((r) => setAllDocs(r.documents));
  }, [name]);

  const handleAssign = async () => {
    if (!name || selectedDocs.length === 0) return;
    await api.assignToCollection(name, selectedDocs);
    setIsAssignOpen(false);
    setSelectedDocs([]);
    load();
  };

  const handleRemove = async (docId: string) => {
    if (!name) return;
    await api.removeFromCollection(name, docId);
    load();
  };

  if (!collection) return <PageSection><Content>Loading...</Content></PageSection>;

  const memberDocIds = new Set(collection.members?.map((m) => m.doc_id) || []);
  const availableDocs = allDocs.filter((d) => !memberDocIds.has(d.doc_id));

  return (
    <PageSection>
      <Content component="h1">{collection.name}</Content>
      <Content component="p">{collection.description || 'No description'}</Content>

      <Card style={{ marginBottom: '1rem' }}>
        <CardTitle>Collection Info</CardTitle>
        <CardBody>
          <DescriptionList isHorizontal>
            <DescriptionListGroup>
              <DescriptionListTerm>Milvus Collection</DescriptionListTerm>
              <DescriptionListDescription><code>{collection.name}</code></DescriptionListDescription>
            </DescriptionListGroup>
            <DescriptionListGroup>
              <DescriptionListTerm>Doc ID Prefix</DescriptionListTerm>
              <DescriptionListDescription><code>{collection.doc_id_prefix}</code></DescriptionListDescription>
            </DescriptionListGroup>
            <DescriptionListGroup>
              <DescriptionListTerm>Next Sequence</DescriptionListTerm>
              <DescriptionListDescription>{collection.next_sequence}</DescriptionListDescription>
            </DescriptionListGroup>
            <DescriptionListGroup>
              <DescriptionListTerm>Documents</DescriptionListTerm>
              <DescriptionListDescription>{collection.document_count}</DescriptionListDescription>
            </DescriptionListGroup>
            <DescriptionListGroup>
              <DescriptionListTerm>Created By</DescriptionListTerm>
              <DescriptionListDescription>{collection.created_by}</DescriptionListDescription>
            </DescriptionListGroup>
          </DescriptionList>
        </CardBody>
      </Card>

      <div style={{ marginBottom: '1rem' }}>
        <Button variant="primary" onClick={() => setIsAssignOpen(true)}>
          Assign Documents
        </Button>
      </div>

      <Card>
        <CardTitle>Members ({collection.members?.length || 0})</CardTitle>
        <CardBody>
          <Table aria-label="Collection members">
            <Thead>
              <Tr>
                <Th>Doc ID</Th>
                <Th>Name</Th>
                <Th>Type</Th>
                <Th>Status</Th>
                <Th>Last Ingested</Th>
                <Th>Vectors</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {(collection.members || []).map((member) => (
                <Tr key={member.doc_id}>
                  <Td><Link to={`/documents/${member.doc_id}`}><strong>{member.doc_id}</strong></Link></Td>
                  <Td>{member.name.length > 50 ? member.name.slice(0, 50) + '...' : member.name}</Td>
                  <Td>{member.document_type}</Td>
                  <Td><Label color={member.status === 'active' ? 'green' : 'orange'} isCompact>{member.status}</Label></Td>
                  <Td>{member.last_ingested ? new Date(member.last_ingested).toLocaleDateString() : 'Never'}</Td>
                  <Td>{member.vector_count ?? '-'}</Td>
                  <Td>
                    <Button variant="link" isDanger onClick={() => handleRemove(member.doc_id)}>
                      Remove
                    </Button>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </CardBody>
      </Card>

      <Modal
        variant={ModalVariant.medium}
        title="Assign Documents to Collection"
        isOpen={isAssignOpen}
        onClose={() => setIsAssignOpen(false)}
      >
        <Content component="p">Select documents to add to <strong>{collection.name}</strong>:</Content>
        <div style={{ maxHeight: '400px', overflow: 'auto' }}>
          {availableDocs.map((doc) => (
            <div key={doc.doc_id} style={{ padding: '0.25rem 0' }}>
              <label>
                <input
                  type="checkbox"
                  checked={selectedDocs.includes(doc.doc_id)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedDocs([...selectedDocs, doc.doc_id]);
                    } else {
                      setSelectedDocs(selectedDocs.filter((id) => id !== doc.doc_id));
                    }
                  }}
                />{' '}
                <strong>{doc.doc_id}</strong> — {doc.name.slice(0, 60)}
              </label>
            </div>
          ))}
        </div>
        <div style={{ marginTop: '1rem' }}>
          <Button variant="primary" onClick={handleAssign} isDisabled={selectedDocs.length === 0}>
            Assign ({selectedDocs.length})
          </Button>{' '}
          <Button variant="link" onClick={() => setIsAssignOpen(false)}>
            Cancel
          </Button>
        </div>
      </Modal>
    </PageSection>
  );
}
