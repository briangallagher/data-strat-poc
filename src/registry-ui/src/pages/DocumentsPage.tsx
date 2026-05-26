import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  PageSection,
  Content,
  Toolbar,
  ToolbarContent,
  ToolbarItem,
  Select,
  SelectOption,
  MenuToggle,
  MenuToggleElement,
  Label,
  LabelGroup,
} from '@patternfly/react-core';
import { Table, Thead, Tr, Th, Tbody, Td } from '@patternfly/react-table';
import { api, Document, Collection } from '../api';

export function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string>('');
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  useEffect(() => {
    api.listCollections().then((r) => setCollections(r.collections));
  }, []);

  useEffect(() => {
    const params: { collection?: string; status?: string } = { status: 'active' };
    if (selectedCollection) params.collection = selectedCollection;
    api.listDocuments(params).then((r) => setDocuments(r.documents));
  }, [selectedCollection]);

  return (
    <PageSection>
      <Content component="h1">Documents</Content>
      <Content component="p">All registered documents with their identity and collection membership.</Content>

      <Toolbar>
        <ToolbarContent>
          <ToolbarItem>
            <Select
              toggle={(toggleRef: React.Ref<MenuToggleElement>) => (
                <MenuToggle ref={toggleRef} onClick={() => setIsFilterOpen(!isFilterOpen)} isExpanded={isFilterOpen}>
                  {selectedCollection || 'All collections'}
                </MenuToggle>
              )}
              onSelect={(_e, value) => {
                setSelectedCollection(value as string === 'all' ? '' : (value as string));
                setIsFilterOpen(false);
              }}
              isOpen={isFilterOpen}
              onOpenChange={setIsFilterOpen}
            >
              <SelectOption value="all">All collections</SelectOption>
              {collections.map((c) => (
                <SelectOption key={c.name} value={c.name}>
                  {c.name} ({c.document_count})
                </SelectOption>
              ))}
            </Select>
          </ToolbarItem>
        </ToolbarContent>
      </Toolbar>

      <Table aria-label="Documents table">
        <Thead>
          <Tr>
            <Th>Doc ID</Th>
            <Th>Name</Th>
            <Th>Type</Th>
            <Th>Source</Th>
            <Th>Jurisdiction</Th>
            <Th>Collections</Th>
            <Th>Format</Th>
          </Tr>
        </Thead>
        <Tbody>
          {documents.map((doc) => (
            <Tr key={doc.doc_id}>
              <Td>
                <Link to={`/documents/${doc.doc_id}`}><strong>{doc.doc_id}</strong></Link>
              </Td>
              <Td>{doc.name.length > 60 ? doc.name.slice(0, 60) + '...' : doc.name}</Td>
              <Td>{doc.document_type}</Td>
              <Td>{doc.source_system}</Td>
              <Td>{doc.jurisdiction}</Td>
              <Td>
                <LabelGroup>
                  {doc.collections.map((c) => (
                    <Label key={c} color="blue" isCompact>
                      <Link to={`/collections/${c}`}>{c}</Link>
                    </Label>
                  ))}
                </LabelGroup>
              </Td>
              <Td>{doc.file_format || '-'}</Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </PageSection>
  );
}
