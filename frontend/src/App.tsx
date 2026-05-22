import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { isConfigured } from './lib/supabase';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Layout } from './components/Layout';
import ConfigError from './pages/ConfigError';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import SubmitRequest from './pages/SubmitRequest';
import RequestDetail from './pages/RequestDetail';
import Approvals from './pages/Approvals';
import Properties from './pages/Properties';
import Vendors from './pages/Vendors';
import Inspections from './pages/Inspections';
import Profile from './pages/Profile';


export default function App() {
  if (!isConfigured) return <ConfigError />;

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />

          {/* All protected routes share the authenticated layout */}
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="submit" element={
                <ProtectedRoute allowedRoles={['tenant']}>
                  <SubmitRequest />
                </ProtectedRoute>
              } />
              <Route path="requests/:id" element={<RequestDetail />} />
              <Route path="approvals" element={
                <ProtectedRoute allowedRoles={['manager', 'admin']}>
                  <Approvals />
                </ProtectedRoute>
              } />
              <Route path="inspect" element={
                <ProtectedRoute allowedRoles={['manager', 'inspector', 'admin']}>
                  <Inspections />
                </ProtectedRoute>
              } />
              <Route path="properties" element={<Properties />} />
              <Route path="vendors" element={
                <ProtectedRoute allowedRoles={['manager', 'inspector', 'admin']}>
                  <Vendors />
                </ProtectedRoute>
              } />
              <Route path="profile" element={<Profile />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
