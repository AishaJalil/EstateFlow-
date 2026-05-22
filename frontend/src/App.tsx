import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { isConfigured } from './lib/supabase';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Layout } from './components/Layout';
import { VendorLayout } from './components/VendorLayout';
import ConfigError from './pages/ConfigError';
import Login from './pages/Login';
import VendorRegister from './pages/VendorRegister';
import Dashboard from './pages/Dashboard';
import SubmitRequest from './pages/SubmitRequest';
import RequestDetail from './pages/RequestDetail';
import Approvals from './pages/Approvals';
import Properties from './pages/Properties';
import Vendors from './pages/Vendors';
import Inspections from './pages/Inspections';
import Messages from './pages/Messages';
import CalendarSettings from './pages/CalendarSettings';

export default function App() {
  if (!isConfigured) return <ConfigError />;

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/vendor/register" element={<VendorRegister />} />
          <Route path="/vendor/login" element={<Navigate to="/login?role=vendor" replace />} />

          {/* Vendor portal — Messages + Notifications + Calendar only */}
          <Route element={<ProtectedRoute allowedRoles={['vendor']} />}>
            <Route element={<VendorLayout />}>
              <Route path="/vendor" element={<Navigate to="/vendor/messages" replace />} />
              <Route path="/vendor/messages" element={<Messages />} />
              <Route path="/vendor/calendar" element={<CalendarSettings />} />
            </Route>
          </Route>

          {/* Tenant / manager / inspector / admin */}
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="submit" element={
                <ProtectedRoute allowedRoles={['tenant']}>
                  <SubmitRequest />
                </ProtectedRoute>
              } />
              <Route path="requests/:id" element={<RequestDetail />} />
              <Route path="messages" element={
                <ProtectedRoute allowedRoles={['tenant']}>
                  <Messages />
                </ProtectedRoute>
              } />
              <Route path="calendar" element={
                <ProtectedRoute allowedRoles={['tenant']}>
                  <CalendarSettings />
                </ProtectedRoute>
              } />
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
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
