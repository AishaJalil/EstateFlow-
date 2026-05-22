import { api } from '../lib/api';
import {
  agentLogsFromResponse,
  mapInspection,
  mapMaintenanceRequest,
  mapPredictive,
  mapProperty,
  mapVendor,
  normalizePipeline,
  unwrapData,
} from '../lib/mappers';
import {
  AgentLog,
  AppNotification,
  Inspection,
  MaintenanceRequest,
  PipelineResult,
  PredictiveMaintenance,
  Property,
  UserProfile,
  Vendor,
} from '../types';

export async function fetchProfile(): Promise<UserProfile> {
  const row = unwrapData<Record<string, unknown>>(await api.get('/api/profile/me'));
  return {
    id: String(row.id),
    email: String(row.email ?? ''),
    role: row.role as UserProfile['role'],
    full_name: row.full_name as string | undefined,
    whatsapp_phone: row.whatsapp_phone as string | undefined,
  };
}

export async function updateProfile(body: {
  full_name?: string;
  phone?: string;
  whatsapp_phone?: string;
}): Promise<UserProfile> {
  const row = unwrapData<Record<string, unknown>>(await api.put('/api/profile/me', body));
  return {
    id: String(row.id),
    email: String(row.email ?? ''),
    role: row.role as UserProfile['role'],
    full_name: row.full_name as string | undefined,
    whatsapp_phone: row.whatsapp_phone as string | undefined,
  };
}

export async function fetchMaintenanceRequests(): Promise<MaintenanceRequest[]> {
  const rows = unwrapData<Record<string, unknown>[]>(await api.get('/api/maintenance'));
  return (rows ?? []).map(mapMaintenanceRequest);
}

export async function fetchMaintenanceRequest(id: string): Promise<MaintenanceRequest> {
  const row = unwrapData<Record<string, unknown>>(await api.get(`/api/maintenance/${id}`));
  return mapMaintenanceRequest(row);
}

export async function fetchPendingApprovals(): Promise<MaintenanceRequest[]> {
  const rows = unwrapData<Record<string, unknown>[]>(
    await api.get('/api/maintenance/pending-approvals')
  );
  return (rows ?? []).map(mapMaintenanceRequest);
}

export async function approveMaintenanceRequest(id: string): Promise<void> {
  await api.post(`/api/maintenance/${id}/approve`, { approved: true });
}

export async function resolveMaintenanceRequest(id: string): Promise<void> {
  await api.post(`/api/maintenance/${id}/resolve`);
}

export async function submitFeedback(
  id: string,
  body: { confirmed_resolved: boolean; comment?: string }
): Promise<void> {
  await api.post(`/api/maintenance/${id}/feedback`, body);
}

export async function fetchPipelineLive(id: string): Promise<{
  request: MaintenanceRequest;
  pipeline: PipelineResult | undefined;
  agentLogs: AgentLog[];
}> {
  const [reqRow, pipeRes] = await Promise.all([
    unwrapData<Record<string, unknown>>(api.get(`/api/maintenance/${id}`)),
    api.get<{ pipeline: Record<string, unknown> | null; agent_logs: unknown[] }>(
      `/api/maintenance/${id}/pipeline`
    ),
  ]);

  const agentLogs = agentLogsFromResponse(pipeRes.agent_logs);
  const pipeline = normalizePipeline(pipeRes.pipeline ?? undefined, agentLogs);
  const request = mapMaintenanceRequest(reqRow);
  if (pipeline) request.maintenance_pipeline_results = pipeline;

  return { request, pipeline, agentLogs };
}

export async function submitMaintenanceJson(body: {
  property_id: string;
  property_name: string;
  unit: string;
  original_issue: string;
  latitude?: number;
  longitude?: number;
}): Promise<string> {
  const res = await api.post<{ data: { id: string }; request_id: string }>(
    '/api/maintenance',
    body
  );
  const payload = res as { data?: { id: string }; request_id?: string };
  return payload.data?.id ?? payload.request_id ?? '';
}

export async function submitMaintenanceWithMedia(form: FormData): Promise<string> {
  const res = await api.postForm<{ data: { id: string }; request_id: string }>(
    '/api/maintenance/submit-with-media',
    form
  );
  const payload = res as { data?: { id: string }; request_id?: string };
  return payload.data?.id ?? payload.request_id ?? '';
}

export async function fetchProperties(): Promise<Property[]> {
  const rows = unwrapData<Record<string, unknown>[]>(await api.get('/api/properties'));
  return (rows ?? []).map(mapProperty);
}

export async function createProperty(body: {
  name: string;
  city: string;
  address: string;
  unit_numbers: string[];
  latitude?: number;
  longitude?: number;
}): Promise<void> {
  await api.post('/api/properties', body);
}

export async function fetchVendors(): Promise<Vendor[]> {
  const rows = unwrapData<Record<string, unknown>[]>(await api.get('/api/vendors'));
  return (rows ?? []).map(mapVendor);
}

export async function rateVendor(
  vendorId: string,
  body: { rating: number; comment?: string }
): Promise<void> {
  await api.post(`/api/vendors/${vendorId}/rate`, body);
}

export async function fetchInspections(): Promise<Inspection[]> {
  const rows = unwrapData<Record<string, unknown>[]>(await api.get('/api/inspections'));
  return (rows ?? []).map(mapInspection);
}

export async function createInspection(body: {
  property_id: string;
  property_name: string;
  inspection_type: string;
  items: { item_name: string; result: string; note?: string }[];
  notes?: Record<string, unknown>;
}): Promise<void> {
  await api.post('/api/inspections', body);
}

export async function fetchPredictiveMaintenance(): Promise<PredictiveMaintenance[]> {
  const rows = unwrapData<Record<string, unknown>[]>(
    await api.get('/api/predictive-maintenance')
  );
  return (rows ?? []).map(mapPredictive);
}

export async function runPredictiveMaintenance(): Promise<void> {
  await api.post('/api/predictive-maintenance/run');
}

// ─── Notifications ────────────────────────────────────────────────────────────

export async function fetchNotifications(): Promise<{
  notifications: AppNotification[];
  unread_count: number;
}> {
  const res = await api.get<{ data: AppNotification[]; unread_count: number }>(
    '/api/notifications'
  );
  return { notifications: res.data ?? [], unread_count: res.unread_count ?? 0 };
}

export async function markNotificationRead(id: string): Promise<void> {
  await api.patch(`/api/notifications/${id}/read`, {});
}

export async function markAllNotificationsRead(): Promise<void> {
  await api.patch('/api/notifications/read-all', {});
}


