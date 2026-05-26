import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  Page,
  Masthead,
  MastheadMain,
  MastheadBrand,
  MastheadContent,
  Nav,
  NavItem,
  NavList,
  PageSidebar,
  PageSidebarBody,
  Content,
} from '@patternfly/react-core';
import { DocumentsPage } from './pages/DocumentsPage';
import { DocumentDetailPage } from './pages/DocumentDetailPage';
import { CollectionsPage } from './pages/CollectionsPage';
import { CollectionDetailPage } from './pages/CollectionDetailPage';
import { CreateCollectionPage } from './pages/CreateCollectionPage';

function AppNav() {
  const location = useLocation();

  return (
    <Nav>
      <NavList>
        <NavItem isActive={location.pathname === '/' || location.pathname.startsWith('/documents')}>
          <Link to="/documents">Documents</Link>
        </NavItem>
        <NavItem isActive={location.pathname.startsWith('/collections')}>
          <Link to="/collections">Collections</Link>
        </NavItem>
      </NavList>
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
        <Content component="small">Data Strategy POC v2 — M3 Connectors</Content>
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
        </Routes>
      </Page>
    </BrowserRouter>
  );
}
