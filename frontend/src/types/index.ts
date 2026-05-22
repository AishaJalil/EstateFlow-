export type UserRole = 'tenant' | 'manager' | 'inspector' | 'admin';

export interface UserProfile {
  id: string;
  email: string;
  role: UserRole;
  full_name?: string;
  whatsapp_phone?: string;
}

export interface AppNotification {
  id: string;
  type: 'in_app' | 'sms' | 'email' | 'whatsapp';
  subject?: string;
  message: string;
  reference_type?: string;
  reference_id?: string;
  status: string;
  read_at?: string;
  created_at: string;
}

export type RequestStatus =
  | 'Open'
  | 'In Progress'
  | 'Scheduled'
  | 'Resolved'
  | 'Pending Approval'
  | 'Blocked';

export type UrgencyLevel = 'Critical' | 'High' | 'Medium' | 'Low';

export interface AgentLog {
  agent_name: string;
  duration_ms: number;
  success: boolean;
  output: Record<string, unknown>;
}

export interface PerformanceAlert {
  type: string;
  message: string;
}

export interface PipelineResult {
  urgency?: UrgencyLevel;
  category?: string;
  summary?: string;
  assigned_vendor?: string;
  assigned_vendor_id?: string;
  scheduled_time?: string;
  sla_target_hours?: number;
  agents_run?: AgentLog[];
  report_summary?: string;
  report_pending_signature?: boolean;
  report_signed?: boolean;
  human_approved?: boolean;
  token_usage_estimate?: number;
  performance_alerts?: PerformanceAlert[];
  recommended_model?: string;
}


export interface MaintenanceRequest {
  id: string;
  ticket_id: string;
  tenant_name: string;
  property_name: string;
  unit: string;
  original_issue: string;
  status: RequestStatus;
  created_at: string;
  maintenance_pipeline_results?: PipelineResult;
  tenant_confirmed_resolved?: boolean;
  tenant_feedback?: string;
}

export interface Property {
  id: string;
  name: string;
  city: string;
  address: string;
  units: string[];
  lat?: number;
  lng?: number;
  created_at?: string;
}

export interface Vendor {
  id: string;
  name: string;
  specialty: string;
  city: string;
  rating: number;
  assignments: number;
  distance_km?: number;
  phone?: string;
  email?: string;
  whatsapp_phone?: string;
}

export interface Inspection {
  id: string;
  property_id: string;
  property_name: string;
  inspector_name: string;
  scheduled_date: string;
  status: 'Scheduled' | 'In Progress' | 'Completed' | 'Cancelled';
  risk_score?: number;
  ai_summary?: string;
  created_at: string;
}

export interface PredictiveMaintenance {
  property_id: string;
  property_name: string;
  risk_score: number;
  recurring_patterns_count: number;
  next_predicted_issue?: string;
  forecast_date?: string;
}

export type AgentStepStatus = 'pending' | 'running' | 'done' | 'failed';

export interface AgentStep {
  key: string;
  label: string;
  description: string;
  status: AgentStepStatus;
  duration_ms?: number;
  output?: Record<string, unknown>;
}
