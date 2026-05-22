/** Keep in sync with backend LangGraph agent node names. */
export const PIPELINE_ORDER = [
  'security_agent',
  'complaint_agent',
  'priority_agent',
  'compliance_agent',
  'vendor_matching_agent',
  'governance_ethics_agent',
  'vendor_outreach_agent',
  'scheduling_agent',
  'communications_agent',
  'report_agent',
  'performance_agent',
] as const;

export function isPipelineComplete(
  agentsRun: string[],
  status?: string
): boolean {
  return (
    agentsRun.includes('performance_agent') ||
    status === 'Blocked' ||
    (status === 'Pending Approval' &&
      agentsRun.includes('report_agent') &&
      !agentsRun.includes('performance_agent'))
  );
}
