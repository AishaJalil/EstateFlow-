import { useEffect, useState } from 'react';
import { Bell } from 'lucide-react';
import { fetchNotifications } from '../services/estateflow';
import type { AppNotification } from '../types';

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[]>([]);

  useEffect(() => {
    fetchNotifications()
      .then(setItems)
      .catch(() => setItems([]));
  }, [open]);

  const unread = items.filter((n) => n.status === 'pending').length;

  return (
    <div className="relative px-3 pb-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-teal-100 hover:bg-white/10 hover:text-white text-sm"
        aria-label="Notifications"
      >
        <Bell size={18} />
        <span>Notifications</span>
        {unread > 0 && (
          <span className="ml-auto text-xs bg-amber-400 text-amber-900 font-bold px-1.5 py-0.5 rounded-full">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute left-3 right-3 bottom-full mb-1 max-h-64 overflow-y-auto bg-white rounded-lg shadow-lg border border-gray-100 z-50">
          {items.length === 0 ? (
            <p className="p-3 text-xs text-gray-500">No notifications</p>
          ) : (
            items.slice(0, 8).map((n) => (
              <div key={n.id} className="px-3 py-2 border-b border-gray-50 last:border-0">
                <p className="text-xs font-semibold text-gray-800">{n.subject ?? 'Update'}</p>
                <p className="text-xs text-gray-600 line-clamp-2">{n.message}</p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
