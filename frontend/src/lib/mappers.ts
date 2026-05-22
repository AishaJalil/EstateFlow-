import {
  AgentLog,
  Inspection,
  MaintenanceRequest,
  PipelineResult,
  PredictiveMaintenance,
  Property,
  Vendor,
} from '../types';

/** Backend wraps most list/detail payloads in `{ data: T }`. */
export function unwrapData<T>(payload: unknown): T {
  if (payload !== null && typeof payload === 'object' && 'data' in payload) {
    return (payload as { data: T }).data;
  }
  return payload as T;
}

export function getPipelineFromRow(
  row: Record<string, unknown>
): PipelineResult | undefined {
  const pl = row.maintenance_pipeline_results;
  if (!pl) return undefined;
  if (Array.isArray(pl)) return normalizePipeline(pl[0] as Record<string, unknown>);
  return normalizePipeline(pl as Record<string, unknown>);
}

export function normalizePipeline(
  raw: Record<string, unknown> | null | undefined,
  agentLogs?: AgentLog[]
): PipelineResult | undefined {
  if (!raw && !agentLogs?.length) return undefined;

  const alertsRaw = raw?.performance_alerts;
  const performance_alerts = Array.isArray(alertsRaw)
    ? alertsRaw.map((a) =>
        typeof a === 'string'
          ? { type: 'alert', message: a }
          : { type: String((a as Record<string, unknown>).type ?? 'alert'), message: String((a as Record<string, unknown>).message ?? a) }
      )
    : undefined;

  return {
    urgency: raw?.urgency as PipelineResult['urgency'],
    category: raw?.category as string | undefined,
    summary: raw?.summary as string | undefined,
    assigned_vendor: raw?.assigned_vendor as string | undefined,
    assigned_vendor_id: raw?.assigned_vendor_id as string | undefined,
    scheduled_time: raw?.scheduled_time as string | undefined,
    sla_target_hours: raw?.sla_target_hours as number | undefined,
    agents_run: agentLogs,
    report_summary: raw?.report_summary as string | undefined,
    report_pending_signature: Boolean(raw?.report_pending_signature),
    report_signed: Boolean(raw?.report_signed),
    token_usage_estimate: raw?.token_usage_estimate as number | undefined,
    performance_alerts,
    recommended_model: raw?.recommended_model as string | undefined,
    human_approved: Boolean(raw?.human_approved),
  };

}

export function mapMaintenanceRequest(row: Record<string, unknown>): MaintenanceRequest {
  return {
    id: String(row.id),
    ticket_id: String(row.ticket_id ?? ''),
    tenant_name: String(row.tenant_name ?? 'Tenant'),
    property_name: String(row.property_name ?? ''),
    unit: String(row.unit ?? ''),
    original_issue: String(row.original_issue ?? ''),
    status: row.status as MaintenanceRequest['status'],
    created_at: String(row.created_at ?? ''),
    maintenance_pipeline_results: getPipelineFromRow(row),
    tenant_confirmed_resolved: row.tenant_confirmed_resolved as boolean | undefined,
    tenant_feedback: row.tenant_feedback as string | undefined,
  };
}


export function mapProperty(row: Record<string, unknown>): Property {
  const unitsRaw = row.units as { unit_number?: string }[] | undefined;
  return {
    id: String(row.id),
    name: String(row.name ?? ''),
    city: String(row.city ?? ''),
    address: String(row.address ?? ''),
    units: (unitsRaw ?? []).map((u) => String(u.unit_number ?? '')).filter(Boolean),
    lat: row.latitude as number | undefined,
    lng: row.longitude as number | undefined,
    created_at: row.created_at as string | undefined,
  };
}

export function mapVendor(row: Record<string, unknown>): Vendor {
  return {
    id: String(row.id),
    name: String(row.name ?? ''),
    specialty: String(row.specialty ?? 'General'),
    city: String(row.city ?? row.area ?? ''),
    rating: Number(row.rating ?? 5),
    assignments: Number(row.total_assignments ?? 0),
    phone: row.phone as string | undefined,
    email: row.email as string | undefined,
  };
}

export function mapInspection(row: Record<string, unknown>): Inspection {
  const pl = row.inspection_pipeline_results;
  const pipeline = Array.isArray(pl) ? pl[0] : pl;
  const pr = pipeline as Record<string, unknown> | undefined;

  const riskMap: Record<string, number> = {
    Low: 0.25,
    Medium: 0.5,
    High: 0.75,
    Critical: 0.9,
  };

  return {
    id: String(row.id),
    property_id: String(row.property_id ?? ''),
    property_name: String(row.property_name ?? ''),
    inspector_name: String(row.inspector_name ?? ''),
    scheduled_date: String(row.created_at ?? ''),
    status: (row.status as Inspection['status']) ?? 'Completed',
    risk_score: pr?.risk_level ? riskMap[String(pr.risk_level)] ?? 0.5 : undefined,
    ai_summary: pr?.executive_summary as string | undefined,
    created_at: String(row.created_at ?? ''),
  };
}

export function mapPredictive(row: Record<string, unknown>): PredictiveMaintenance {
  const recurring = (row.recurring_issues as unknown[]) ?? [];
  const forecasts = (row.failure_forecasts as { forecast?: string }[]) ?? [];
  const risk = Number(row.risk_score ?? 0);

  return {
    property_id: String(row.property_id ?? row.id ?? ''),
    property_name: String(row.property_name ?? 'Property'),
    risk_score: risk > 1 ? risk / 100 : risk,
    recurring_patterns_count: recurring.length,
    next_predicted_issue: forecasts[0]?.forecast,
    forecast_date: row.created_at as string | undefined,
  };
}

export function agentLogsFromResponse(logs: unknown): AgentLog[] {
  if (!Array.isArray(logs)) return [];
  return logs.map((l) => {
    const row = l as Record<string, unknown>;
    return {
      agent_name: String(row.agent_name ?? ''),
      duration_ms: Number(row.duration_ms ?? 0),
      success: Boolean(row.success ?? true),
      output: (row.output as Record<string, unknown>) ?? {},
    };
  });
}
