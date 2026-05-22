import { api } from '../lib/api';
import { hasVendorToken } from '../lib/vendorAuth';
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
  Inspection,
  MaintenanceRequest,
  PipelineResult,
  PredictiveMaintenance,
  Property,
  UserProfile,
  Vendor,
  Message,
  MessageThread,
  AppNotification,
} from '../types';

export async function fetchProfile(): Promise<UserProfile> {
  const path = hasVendorToken() ? '/api/vendors/me' : '/api/profile/me';
  const row = unwrapData<Record<string, unknown>>(await api.get(path));
  return {
    id: String(row.id),
    email: String(row.email ?? ''),
    role: row.role as UserProfile['role'],
    full_name: row.full_name as string | undefined,
  };
}

export async function loginVendor(
  email: string,
  password: string
): Promise<{ access_token: string; vendor: { id: string; name: string; email?: string } }> {
  const res = unwrapData<{
    access_token: string;
    vendor: { id: string; name: string; email?: string };
  }>(await api.post('/api/vendors/login', { email, password }, false));
  return res;
}

export async function registerVendor(body: {
  name: string;
  email: string;
  password: string;
  specialty: string;
  phone: string;
  latitude?: number;
  longitude?: number;
  city?: string;
  area?: string;
}): Promise<{ access_token: string; vendor: { id: string; name: string; email?: string } }> {
  const res = unwrapData<{
    access_token: string;
    vendor: { id: string; name: string; email?: string };
  }>(await api.post('/api/vendors/register', body, false));
  return res;
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

export async function fetchMessageThreads(): Promise<MessageThread[]> {
  const rows = unwrapData<MessageThread[]>(await api.get('/api/messaging/threads'));
  return rows ?? [];
}

export async function fetchMessageThread(
  threadId: string
): Promise<{ messages: Message[]; thread: MessageThread }> {
  const res = await api.get<{ data: Message[]; thread: MessageThread }>(
    `/api/messaging/threads/${threadId}/messages`
  );
  return { messages: res.data ?? [], thread: res.thread };
}

export async function sendThreadMessage(threadId: string, body: string): Promise<void> {
  await api.post(`/api/messaging/threads/${threadId}/messages`, { body });
}

export async function fetchNotifications(): Promise<AppNotification[]> {
  const rows = unwrapData<AppNotification[]>(await api.get('/api/notifications'));
  return rows ?? [];
}

export async function fetchCalendarStatus(): Promise<{ connected: boolean }> {
  const res = unwrapData<{ connected: boolean; profile_id: string }>(
    await api.get('/api/calendar/status')
  );
  return { connected: res.connected };
}

export async function startCalendarConnect(): Promise<{ auth_url: string }> {
  const res = unwrapData<{ auth_url: string; state: string }>(
    await api.get('/api/calendar/connect')
  );
  return { auth_url: res.auth_url };
}

export async function disconnectCalendar(): Promise<void> {
  await api.delete('/api/calendar/disconnect');
}
