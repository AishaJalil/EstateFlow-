import { useEffect, useState } from 'react';
import { Calendar, CheckCircle2, Link2 } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import {
  disconnectCalendar,
  fetchCalendarStatus,
  startCalendarConnect,
} from '../services/estateflow';

export default function CalendarSettings() {
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [params] = useSearchParams();

  useEffect(() => {
    fetchCalendarStatus()
      .then((s) => setConnected(s.connected))
      .finally(() => setLoading(false));
  }, [params.get('connected')]);

  async function handleConnect() {
    const { auth_url } = await startCalendarConnect();
    window.location.href = auth_url;
  }

  async function handleDisconnect() {
    await disconnectCalendar();
    setConnected(false);
  }

  return (
    <div className="max-w-lg space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Google Calendar</h1>
      <p className="text-sm text-gray-500">
        Connect your personal Google Calendar so the EstateFlow agent can book maintenance visits
        on your calendar when you confirm a job. Tokens are stored securely per account — not shared
        with other tenants or vendors.
      </p>

      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Calendar className="text-teal-700" size={28} />
          <div>
            <p className="font-semibold text-gray-900">Connection status</p>
            {loading ? (
              <p className="text-sm text-gray-500">Checking…</p>
            ) : connected ? (
              <p className="text-sm text-green-700 flex items-center gap-1">
                <CheckCircle2 size={14} /> Connected via MCP calendar tools
              </p>
            ) : (
              <p className="text-sm text-gray-500">Not connected</p>
            )}
          </div>
        </div>

        {params.get('connected') === '1' && (
          <p className="text-sm text-green-700 mb-4 bg-green-50 rounded-lg px-3 py-2">
            Calendar connected successfully.
          </p>
        )}

        {connected ? (
          <button
            type="button"
            onClick={handleDisconnect}
            className="text-sm text-red-600 hover:underline"
          >
            Disconnect calendar
          </button>
        ) : (
          <button
            type="button"
            onClick={handleConnect}
            className="flex items-center gap-2 bg-teal-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            <Link2 size={16} />
            Connect Google Calendar
          </button>
        )}
      </div>
    </div>
  );
}
