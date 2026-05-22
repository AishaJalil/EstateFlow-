import { useEffect, useState, FormEvent } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Building2, Home, Calendar, FileText,
  PenSquare, CheckCircle2, Clock, AlertCircle, Star,
  ThumbsUp, ThumbsDown, MessageSquare, RefreshCw
} from 'lucide-react';
import {
  fetchMaintenanceRequest,
  resolveMaintenanceRequest,
  submitFeedback,
  rateVendor,
} from '../services/estateflow';
import { MaintenanceRequest } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { UrgencyBadge } from '../components/UrgencyBadge';
import { AgentPipelineLive } from '../components/AgentPipelineLive';
import { Skeleton } from '../components/LoadingSkeleton';
import { useAuth } from '../contexts/AuthContext';

export default function RequestDetail() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const live = searchParams.get('live') === '1';
  const { role } = useAuth();

  const [request, setRequest] = useState<MaintenanceRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function reload() {
    if (!id) return;
    try {
      setRequest(await fetchMaintenanceRequest(id));
    } catch {
      setError('Could not load request.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { reload(); }, [id]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <Skeleton className="h-6 w-40" />
        <div className="bg-white rounded-xl p-5 space-y-3 border border-gray-100">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </div>
    );
  }

  if (error || !request) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-5 py-4">
          <AlertCircle size={18} className="text-red-500" />
          <p className="text-sm text-red-700">{error || 'Request not found.'}</p>
        </div>
      </div>
    );
  }

  const pipeline = request.maintenance_pipeline_results;
  const isTenant = role === 'tenant';
  const isResolvable = isTenant && ['In Progress', 'Scheduled'].includes(request.status);
  const isResolved = request.status === 'Resolved';
  const hasVendor = !!pipeline?.assigned_vendor;
  const hasRated = false; // optimistically managed below

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      {/* Back */}
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors">
        <ArrowLeft size={15} />
        Back to dashboard
      </Link>

      {/* Header card */}
      <div className="bg-white rounded-xl shadow-card border border-gray-100 p-5">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{request.ticket_id}</span>
              <StatusBadge status={request.status} />
              {pipeline?.urgency && <UrgencyBadge level={pipeline.urgency} />}
            </div>
            <h1 className="text-lg font-bold text-gray-900">{request.original_issue}</h1>
          </div>
          <p className="text-xs text-gray-400 flex-shrink-0">
            {new Date(request.created_at).toLocaleString()}
          </p>
        </div>

        <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
          <InfoItem icon={<Building2 size={14} />} label="Property" value={request.property_name} />
          <InfoItem icon={<Home size={14} />} label="Unit" value={request.unit} />
          <InfoItem icon={<Clock size={14} />} label="Tenant" value={request.tenant_name} />
          {pipeline?.category && <InfoItem icon={<FileText size={14} />} label="Category" value={pipeline.category} />}
          {pipeline?.sla_target_hours != null && (
            <InfoItem icon={<Clock size={14} />} label="SLA" value={`${pipeline.sla_target_hours}h`} />
          )}
          {pipeline?.scheduled_time && (
            <InfoItem icon={<Calendar size={14} />} label="Scheduled" value={new Date(pipeline.scheduled_time).toLocaleDateString()} />
          )}
          {pipeline?.assigned_vendor && (
            <InfoItem icon={<Building2 size={14} />} label="Vendor" value={pipeline.assigned_vendor} />
          )}
        </div>
      </div>

      {/* Live pipeline */}
      {id && <AgentPipelineLive requestId={id} live={live} />}

      {/* ── Tenant Actions ─────────────────────────────────────────── */}
      {isTenant && (
        <div className="space-y-4">
          {/* Mark as resolved */}
          {isResolvable && (
            <TenantResolveCard requestId={request.id} onResolved={reload} />
          )}

          {/* Follow-up feedback (only if Resolved and not yet confirmed) */}
          {isResolved && !request.tenant_confirmed_resolved && (
            <TenantFeedbackCard requestId={request.id} onSubmitted={reload} />
          )}

          {/* Confirmed resolved */}
          {isResolved && request.tenant_confirmed_resolved && (
            <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-xl px-5 py-4">
              <CheckCircle2 size={18} className="text-green-600" />
              <p className="text-sm font-medium text-green-800">
                You confirmed this issue was resolved.{' '}
                {request.tenant_feedback && (
                  <span className="font-normal text-green-700">"{request.tenant_feedback}"</span>
                )}
              </p>
            </div>
          )}

          {/* Vendor rating — show if resolved and vendor was assigned */}
          {isResolved && hasVendor && pipeline?.assigned_vendor_id && (
            <VendorRatingCard
              vendorName={pipeline.assigned_vendor!}
              vendorId={pipeline.assigned_vendor_id}
            />
          )}

        </div>
      )}

      {/* Report section */}
      {pipeline && (
        <div className="bg-white rounded-xl shadow-card border border-gray-100 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <FileText size={15} className="text-gray-400" />
            Report
          </h2>

          {pipeline.report_summary && (
            <p className="text-sm text-gray-700 leading-relaxed">{pipeline.report_summary}</p>
          )}

          <div className="flex items-center gap-3">
            {pipeline.report_signed ? (
              <div className="flex items-center gap-2 text-green-600 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                <CheckCircle2 size={15} />
                <span className="text-sm font-medium">Report signed</span>
              </div>
            ) : pipeline.report_pending_signature ? (
              <div className="flex items-center gap-2 text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                <PenSquare size={15} />
                <span className="text-sm font-medium">Draft — awaiting manager signature</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-gray-500 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                <FileText size={15} />
                <span className="text-sm">Report not yet generated</span>
              </div>
            )}

            {(request.status === 'Pending Approval' || pipeline.report_pending_signature) && (
              <Link
                to="/approvals"
                className="text-sm text-teal-700 font-medium hover:underline ml-auto"
              >
                Go to Approvals →
              </Link>
            )}
          </div>

          {pipeline.recommended_model && (
            <p className="text-xs text-gray-400">Recommended model: {pipeline.recommended_model}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Subcomponents ────────────────────────────────────────────────────────────

function InfoItem({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-gray-400 mt-0.5 flex-shrink-0">{icon}</span>
      <div>
        <p className="text-xs text-gray-400">{label}</p>
        <p className="text-sm font-medium text-gray-900">{value}</p>
      </div>
    </div>
  );
}

function TenantResolveCard({ requestId, onResolved }: { requestId: string; onResolved: () => void }) {
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handle() {
    setLoading(true);
    try {
      await resolveMaintenanceRequest(requestId);
      setDone(true);
      setTimeout(onResolved, 800);
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-xl px-5 py-4">
        <CheckCircle2 size={18} className="text-green-600" />
        <p className="text-sm font-medium text-green-800">Marked as resolved!</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-card border border-gray-100 p-5">
      <h2 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
        <CheckCircle2 size={15} className="text-teal-700" />
        Issue Fixed?
      </h2>
      <p className="text-xs text-gray-500 mb-4">
        If the vendor has already resolved your issue, you can mark this request as resolved.
      </p>
      <button
        id="resolve-request-btn"
        onClick={handle}
        disabled={loading}
        className="flex items-center gap-2 bg-teal-700 hover:bg-teal-800 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
      >
        {loading ? <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" /> : <CheckCircle2 size={15} />}
        {loading ? 'Marking…' : 'Mark as Resolved'}
      </button>
    </div>
  );
}

function TenantFeedbackCard({ requestId, onSubmitted }: { requestId: string; onSubmitted: () => void }) {
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handle(resolved: boolean) {
    setSubmitting(true);
    try {
      await submitFeedback(requestId, { confirmed_resolved: resolved, comment: comment || undefined });
      setSubmitted(true);
      setTimeout(onSubmitted, 800);
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-xl px-5 py-4">
        <CheckCircle2 size={18} className="text-green-600" />
        <p className="text-sm font-medium text-green-800">Thanks for your feedback!</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-card border border-gray-100 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
        <MessageSquare size={15} className="text-teal-700" />
        Did this resolve your issue?
      </h2>
      <p className="text-xs text-gray-500">
        Your vendor was marked as having visited. Was your issue resolved?
      </p>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={2}
        placeholder="Optional: add any comments…"
        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all resize-none"
      />
      <div className="flex gap-3">
        <button
          id="feedback-yes-btn"
          onClick={() => handle(true)}
          disabled={submitting}
          className="flex items-center gap-2 bg-green-600 hover:bg-green-700 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <ThumbsUp size={14} />
          Yes, resolved
        </button>
        <button
          id="feedback-no-btn"
          onClick={() => handle(false)}
          disabled={submitting}
          className="flex items-center gap-2 bg-red-100 hover:bg-red-200 disabled:opacity-60 text-red-700 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <ThumbsDown size={14} />
          No, still open
        </button>
      </div>
    </div>
  );
}

function VendorRatingCard({
  vendorName,
  vendorId,
}: {
  vendorName: string;
  vendorId: string;
}) {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!rating) { setError('Please select a star rating.'); return; }
    setError('');
    setSubmitting(true);
    try {
      await rateVendor(vendorId, { rating, comment: comment || undefined });
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rating failed.');
    } finally {
      setSubmitting(false);
    }
  }


  if (submitted) {
    return (
      <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-xl px-5 py-4">
        <Star size={18} className="text-amber-500 fill-amber-500" />
        <p className="text-sm font-medium text-amber-800">
          Thanks for rating {vendorName}!
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-card border border-gray-100 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
        <Star size={15} className="text-amber-500" />
        Rate your vendor
      </h2>
      <p className="text-xs text-gray-500">How was your experience with <strong>{vendorName}</strong>?</p>

      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Star picker */}
        <div className="flex gap-1.5">
          {[1, 2, 3, 4, 5].map((s) => (
            <button
              key={s}
              type="button"
              id={`star-${s}`}
              onMouseEnter={() => setHover(s)}
              onMouseLeave={() => setHover(0)}
              onClick={() => setRating(s)}
              className="transition-transform hover:scale-110"
            >
              <Star
                size={28}
                className={
                  s <= (hover || rating)
                    ? 'text-amber-400 fill-amber-400'
                    : 'text-gray-200 fill-gray-200'
                }
              />
            </button>
          ))}
          {rating > 0 && (
            <span className="ml-2 self-center text-sm font-medium text-gray-600">
              {['', 'Poor', 'Fair', 'Good', 'Very Good', 'Excellent'][rating]}
            </span>
          )}
        </div>

        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={2}
          placeholder="Optional: tell us more…"
          className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 resize-none transition-all"
        />

        {error && <p className="text-xs text-red-500">{error}</p>}

        <button
          type="submit"
          id="submit-rating-btn"
          disabled={submitting || !rating}
          className="flex items-center gap-2 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          {submitting ? <RefreshCw size={14} className="animate-spin" /> : <Star size={14} />}
          {submitting ? 'Submitting…' : 'Submit Rating'}
        </button>
      </form>
    </div>
  );
}
