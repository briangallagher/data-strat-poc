import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import {
  Page,
  Masthead,
  MastheadMain,
  MastheadBrand,
  MastheadContent,
  Nav,
  NavItem,
  NavList,
  NavGroup,
  PageSidebar,
  PageSidebarBody,
  Content,
  Divider,
} from '@patternfly/react-core';
import { DocumentsPage } from './pages/DocumentsPage';
import { DocumentDetailPage } from './pages/DocumentDetailPage';
import { CollectionsPage } from './pages/CollectionsPage';
import { CollectionDetailPage } from './pages/CollectionDetailPage';
import { CreateCollectionPage } from './pages/CreateCollectionPage';
import { QueryTracesPage } from './pages/QueryTracesPage';
import { TraceDetailPage } from './pages/TraceDetailPage';
import { DocumentProvenancePage } from './pages/DocumentProvenancePage';
import { CollectionHealthPage } from './pages/CollectionHealthPage';
import { AppOverviewPage } from './pages/AppOverviewPage';
import { ImpactAnalysisPage } from './pages/ImpactAnalysisPage';
import { RegisterDocumentsPage } from './pages/RegisterDocumentsPage';
import { api } from './api';

function AppNav() {
  const location = useLocation();
  const [links, setLinks] = useState<{ marquez_web?: string; mlflow?: string; marquez_lineage?: string; kfp_dashboard?: string; kfp_namespace?: string }>({});

  useEffect(() => {
    api.getExternalLinks().then(setLinks).catch(() => {});
  }, []);

  return (
    <Nav>
      <NavList>
        <NavItem isActive={location.pathname === '/' || location.pathname.startsWith('/documents')}>
          <Link to="/documents">Documents</Link>
        </NavItem>
        <NavItem isActive={location.pathname.startsWith('/collections') && !location.pathname.startsWith('/collections/health')}>
          <Link to="/collections">Collections</Link>
        </NavItem>
        <NavItem isActive={location.pathname.startsWith('/traces')}>
          <Link to="/traces">Queries</Link>
        </NavItem>
        <NavItem isActive={location.pathname === '/health'}>
          <Link to="/health">Collection Health</Link>
        </NavItem>
        <NavItem isActive={location.pathname === '/apps'}>
          <Link to="/apps">Applications</Link>
        </NavItem>
        <NavItem isActive={location.pathname === '/impact'}>
          <Link to="/impact">Impact Analysis</Link>
        </NavItem>
        <NavItem isActive={location.pathname === '/register'}>
          <Link to="/register">Register Documents</Link>
        </NavItem>
      </NavList>
      {(links.marquez_lineage || links.mlflow) && (
        <>
          <Divider />
          <NavGroup title="Observability">
            {links.marquez_lineage && (
              <NavItem>
                <a href={links.marquez_lineage} target="_blank" rel="noopener noreferrer">Marquez Lineage ↗</a>
              </NavItem>
            )}
            {links.mlflow && (
              <NavItem>
                <a href={links.mlflow} target="_blank" rel="noopener noreferrer">MLflow ↗</a>
              </NavItem>
            )}
            {links.kfp_dashboard && links.kfp_namespace && (
              <NavItem>
                <a href={`${links.kfp_dashboard}/develop-train/pipelines/runs/${links.kfp_namespace}`} target="_blank" rel="noopener noreferrer">KFP Pipelines ↗</a>
              </NavItem>
            )}
          </NavGroup>
        </>
      )}
    </Nav>
  );
}

export function App() {
  const header = (
    <Masthead>
      <MastheadMain>
        <MastheadBrand>
          <Content component="h1">Document Registry</Content>
        </MastheadBrand>
      </MastheadMain>
      <MastheadContent>
        <Content component="small">Data Strategy POC v2 — M5 Agentic</Content>
      </MastheadContent>
    </Masthead>
  );

  const sidebar = (
    <PageSidebar>
      <PageSidebarBody>
        <AppNav />
      </PageSidebarBody>
    </PageSidebar>
  );

  return (
    <BrowserRouter>
      <Page masthead={header} sidebar={sidebar}>
        <Routes>
          <Route path="/" element={<DocumentsPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/:docId" element={<DocumentDetailPage />} />
          <Route path="/collections" element={<CollectionsPage />} />
          <Route path="/collections/new" element={<CreateCollectionPage />} />
          <Route path="/collections/:name" element={<CollectionDetailPage />} />
          <Route path="/traces" element={<QueryTracesPage />} />
          <Route path="/traces/:traceId" element={<TraceDetailPage />} />
          <Route path="/documents/:docId/provenance" element={<DocumentProvenancePage />} />
          <Route path="/health" element={<CollectionHealthPage />} />
          <Route path="/apps" element={<AppOverviewPage />} />
          <Route path="/impact" element={<ImpactAnalysisPage />} />
          <Route path="/register" element={<RegisterDocumentsPage />} />
        </Routes>
      </Page>
    </BrowserRouter>
  );
}
