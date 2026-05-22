import { useEffect, useRef, useState } from 'react';
import { Bell, X, CheckCheck, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../services/estateflow';
import { AppNotification } from '../types';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  async function load() {
    setLoading(true);
    try {
      const { notifications: n, unread_count } = await fetchNotifications();
      setNotifications(n);
      setUnread(unread_count);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000); // poll every 30s
    return () => clearInterval(interval);
  }, []);

  // Close panel when clicking outside
  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  async function handleMarkAllRead() {
    await markAllNotificationsRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, read_at: new Date().toISOString() })));
    setUnread(0);
  }

  async function handleMarkRead(id: string) {
    await markNotificationRead(id);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n))
    );
    setUnread((u) => Math.max(0, u - 1));
  }

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell button */}
      <button
        id="notification-bell"
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 rounded-lg text-teal-100 hover:bg-white/10 hover:text-white transition-colors"
        aria-label="Notifications"
      >
        <Bell size={18} />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {/* Slide-out panel */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 sm:w-96 bg-white rounded-xl shadow-2xl border border-gray-100 z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <Bell size={15} className="text-teal-700" />
              <span className="text-sm font-semibold text-gray-900">Notifications</span>
              {unread > 0 && (
                <span className="text-xs bg-red-100 text-red-700 font-bold px-1.5 py-0.5 rounded-full">
                  {unread} new
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {unread > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="flex items-center gap-1 text-xs text-teal-700 hover:text-teal-900 font-medium transition-colors"
                >
                  <CheckCheck size={13} />
                  Mark all read
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* List */}
          <div className="max-h-[420px] overflow-y-auto divide-y divide-gray-50">
            {loading && notifications.length === 0 ? (
              <div className="flex items-center justify-center py-10">
                <div className="w-5 h-5 border-2 border-teal-200 border-t-teal-600 rounded-full animate-spin" />
              </div>
            ) : notifications.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-10 text-center px-4">
                <Bell size={24} className="text-gray-200" />
                <p className="text-sm text-gray-400">No notifications yet</p>
              </div>
            ) : (
              notifications.map((n) => {
                const isUnread = !n.read_at;
                const linkTo =
                  n.reference_type === 'maintenance_request' && n.reference_id
                    ? `/requests/${n.reference_id}`
                    : null;

                return (
                  <div
                    key={n.id}
                    onClick={() => isUnread && handleMarkRead(n.id)}
                    className={`px-4 py-3 cursor-pointer transition-colors hover:bg-gray-50 ${
                      isUnread ? 'bg-teal-50/40' : ''
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* Unread dot */}
                      <div
                        className={`w-2 h-2 rounded-full flex-shrink-0 mt-1.5 ${
                          isUnread ? 'bg-teal-500' : 'bg-transparent'
                        }`}
                      />
                      <div className="flex-1 min-w-0">
                        {n.subject && (
                          <p className="text-xs font-semibold text-gray-800 truncate">{n.subject}</p>
                        )}
                        <p className="text-xs text-gray-600 mt-0.5 leading-relaxed line-clamp-3">
                          {n.message}
                        </p>
                        <div className="flex items-center justify-between mt-1.5">
                          <p className="text-[10px] text-gray-400">{timeAgo(n.created_at)}</p>
                          {linkTo && (
                            <Link
                              to={linkTo}
                              onClick={() => setOpen(false)}
                              className="flex items-center gap-0.5 text-[10px] text-teal-600 hover:underline font-medium"
                            >
                              View <ExternalLink size={10} />
                            </Link>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
