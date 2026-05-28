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
import { api, AppInfo } from '../api';

export function AppOverviewPage() {
  const [apps, setApps] = useState<AppInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.listApps()
      .then((data) => {
        setApps(data);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  function workflowColor(type: string): 'blue' | 'purple' | 'grey' {
    if (type === 'deterministic') return 'blue';
    if (type === 'agentic') return 'purple';
    return 'grey';
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
      <Content component="h1">Applications</Content>
      <Content component="p">
        Query applications consuming document collections. Each application is registered
        in Marquez as an OpenLineage job with its consumed collections as inputs.
      </Content>

      {error && <Alert variant="warning" title={error} />}

      <Gallery hasGutter minWidths={{ default: '400px' }}>
        {apps.map((app) => (
          <GalleryItem key={app.app_name}>
            <Card>
              <CardTitle>
                {app.app_name}
                <Label
                  color={workflowColor(app.workflow_type)}
                  isCompact
                  style={{ marginLeft: 8 }}
                >
                  {app.workflow_type}
                </Label>
              </CardTitle>
              <CardBody>
                <DescriptionList isHorizontal isCompact>
                  <DescriptionListGroup>
                    <DescriptionListTerm>Collections</DescriptionListTerm>
                    <DescriptionListDescription>
                      {app.collections.map((coll) => (
                        <Link key={coll} to={`/collections/${coll}`} style={{ marginRight: 4 }}>
                          <Label color="blue" isCompact>{coll}</Label>
                        </Link>
                      ))}
                    </DescriptionListDescription>
                  </DescriptionListGroup>
                  <DescriptionListGroup>
                    <DescriptionListTerm>Queries</DescriptionListTerm>
                    <DescriptionListDescription>
                      <Label color="gold" isCompact>{app.query_count}</Label>
                    </DescriptionListDescription>
                  </DescriptionListGroup>
                  <DescriptionListGroup>
                    <DescriptionListTerm>Last Query</DescriptionListTerm>
                    <DescriptionListDescription>
                      {app.last_query
                        ? new Date(parseInt(app.last_query)).toLocaleDateString()
                        : 'No queries yet'}
                    </DescriptionListDescription>
                  </DescriptionListGroup>
                </DescriptionList>
              </CardBody>
            </Card>
          </GalleryItem>
        ))}
      </Gallery>
    </PageSection>
  );
}
