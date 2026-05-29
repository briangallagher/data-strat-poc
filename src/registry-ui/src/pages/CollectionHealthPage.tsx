import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  PageSection,
  Content,
  Card,
  CardBody,
  CardTitle,
  Gallery,
  GalleryItem,
  Label,
  DescriptionList,
  DescriptionListGroup,
  DescriptionListTerm,
  DescriptionListDescription,
  Spinner,
  Alert,
} from '@patternfly/react-core';
import { api, Collection, CollectionHealth } from '../api';

export function CollectionHealthPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [healthData, setHealthData] = useState<Record<string, CollectionHealth>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.listCollections()
      .then(async (r) => {
        setCollections(r.collections);
        const healthMap: Record<string, CollectionHealth> = {};
        await Promise.all(
          r.collections.map(async (coll) => {
            try {
              const health = await api.getCollectionHealth(coll.name);
              healthMap[coll.name] = health;
            } catch {
              // health endpoint may not be available yet
            }
          })
        );
        setHealthData(healthMap);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  function stalenessColor(days: number | null): 'green' | 'orange' | 'red' | 'grey' {
    if (days === null) return 'grey';
    if (days <= 7) return 'green';
    if (days <= 30) return 'orange';
    return 'red';
  }

  if (loading) {
    return (
      <PageSection>
        <Spinner size="lg" />
      </PageSection>
    );
  }

  return (
    <PageSection>
      <Content component="h1">Collection Health</Content>
      <Content component="p">
        Operational health metrics for each document collection — document count,
        vector count, consuming apps, query volume, and staleness.
      </Content>

      {error && <Alert variant="warning" title={error} />}

      <Gallery hasGutter minWidths={{ default: '400px' }}>
        {collections.map((coll) => {
          const health = healthData[coll.name];
          return (
            <GalleryItem key={coll.name}>
              <Card>
                <CardTitle>
                  <Link to={`/collections/${coll.name}`}>{coll.name}</Link>
                </CardTitle>
                <CardBody>
                  <DescriptionList isHorizontal isCompact>
                    <DescriptionListGroup>
                      <DescriptionListTerm>Documents</DescriptionListTerm>
                      <DescriptionListDescription>
                        <Label color="blue" isCompact>{health?.document_count ?? coll.document_count}</Label>
                      </DescriptionListDescription>
                    </DescriptionListGroup>
                    <DescriptionListGroup>
                      <DescriptionListTerm>Vectors</DescriptionListTerm>
                      <DescriptionListDescription>
                        <Label color="purple" isCompact>
                          {health?.vector_count?.toLocaleString() ?? 'N/A'}
                        </Label>
                      </DescriptionListDescription>
                    </DescriptionListGroup>
                    <DescriptionListGroup>
                      <DescriptionListTerm>Consuming Apps</DescriptionListTerm>
                      <DescriptionListDescription>
                        {health?.consuming_apps?.length ? (
                          health.consuming_apps.map((app) => (
                            <Label key={app} color="teal" isCompact style={{ marginRight: 4 }}>
                              {app}
                            </Label>
                          ))
                        ) : (
                          <span style={{ color: '#666' }}>None</span>
                        )}
                      </DescriptionListDescription>
                    </DescriptionListGroup>
                    <DescriptionListGroup>
                      <DescriptionListTerm>Queries</DescriptionListTerm>
                      <DescriptionListDescription>
                        <Label color="orange" isCompact>{health?.query_count ?? 0}</Label>
                      </DescriptionListDescription>
                    </DescriptionListGroup>
                    <DescriptionListGroup>
                      <DescriptionListTerm>Last Ingest</DescriptionListTerm>
                      <DescriptionListDescription>
                        {health?.last_ingest
                          ? new Date(health.last_ingest).toLocaleDateString()
                          : 'Never'}
                      </DescriptionListDescription>
                    </DescriptionListGroup>
                    <DescriptionListGroup>
                      <DescriptionListTerm>Staleness</DescriptionListTerm>
                      <DescriptionListDescription>
                        <Label
                          color={stalenessColor(health?.staleness_days ?? null)}
                          isCompact
                        >
                          {health?.staleness_days !== null && health?.staleness_days !== undefined
                            ? `${health.staleness_days} days`
                            : 'Unknown'}
                        </Label>
                      </DescriptionListDescription>
                    </DescriptionListGroup>
                  </DescriptionList>
                </CardBody>
              </Card>
            </GalleryItem>
          );
        })}
      </Gallery>
    </PageSection>
  );
}
