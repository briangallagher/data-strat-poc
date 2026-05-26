import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  PageSection,
  Content,
  Button,
  Card,
  CardBody,
  CardTitle,
  Gallery,
  GalleryItem,
  Label,
} from '@patternfly/react-core';
import { api, Collection } from '../api';

export function CollectionsPage() {
  const [collections, setCollections] = useState<Collection[]>([]);

  useEffect(() => {
    api.listCollections().then((r) => setCollections(r.collections));
  }, []);

  return (
    <PageSection>
      <Content component="h1">Collections</Content>
      <Content component="p">
        Logical groupings of documents. Each collection maps to a Milvus vector collection.
      </Content>

      <div style={{ marginBottom: '1rem' }}>
        <Link to="/collections/new">
          <Button variant="primary">Create Collection</Button>
        </Link>
      </div>

      <Gallery hasGutter minWidths={{ default: '300px' }}>
        {collections.map((coll) => (
          <GalleryItem key={coll.name}>
            <Card isClickable>
              <CardTitle>
                <Link to={`/collections/${coll.name}`}>{coll.name}</Link>
              </CardTitle>
              <CardBody>
                <p>{coll.description || 'No description'}</p>
                <div style={{ marginTop: '0.5rem' }}>
                  <Label color="blue" isCompact>{coll.document_count} documents</Label>
                  {' '}
                  <Label color="grey" isCompact>prefix: {coll.doc_id_prefix}</Label>
                </div>
                <div style={{ marginTop: '0.5rem', fontSize: '0.85em', color: '#666' }}>
                  Created by: {coll.created_by}
                </div>
              </CardBody>
            </Card>
          </GalleryItem>
        ))}
      </Gallery>
    </PageSection>
  );
}
