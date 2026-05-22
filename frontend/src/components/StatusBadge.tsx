import { RequestStatus } from '../types';

const styles: Record<RequestStatus, string> = {
  'Open': 'bg-sky-100 text-sky-800 border border-sky-200',
  'In Progress': 'bg-teal-100 text-teal-800 border border-teal-200',
  'Scheduled': 'bg-violet-100 text-violet-800 border border-violet-200',
  'Resolved': 'bg-green-100 text-green-800 border border-green-200',
  'Pending Approval': 'bg-amber-100 text-amber-800 border border-amber-200',
  'Blocked': 'bg-red-100 text-red-800 border border-red-200',
  'Awaiting Vendor': 'bg-orange-100 text-orange-800 border border-orange-200',
};

export function StatusBadge({ status }: { status: RequestStatus }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status]}`}>
      {status}
    </span>
  );
}
