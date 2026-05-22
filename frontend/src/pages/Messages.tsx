import { useCallback, useEffect, useState } from 'react';
import { MessageSquare, Send } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../lib/supabase';
import {
  fetchMessageThread,
  fetchMessageThreads,
  sendThreadMessage,
} from '../services/estateflow';
import type { Message, MessageThread } from '../types';
import { EmptyState } from '../components/EmptyState';
import { TableSkeleton } from '../components/LoadingSkeleton';

export default function Messages() {
  const { role } = useAuth();
  const [threads, setThreads] = useState<MessageThread[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  const loadThreads = useCallback(async () => {
    setLoading(true);
    try {
      const list = await fetchMessageThreads();
      setThreads(list);
      if (!activeId && list.length > 0) setActiveId(list[0].id);
    } finally {
      setLoading(false);
    }
  }, [activeId]);

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  const refreshMessages = useCallback(async (threadId: string) => {
    const res = await fetchMessageThread(threadId);
    setMessages(res.messages);
  }, []);

  useEffect(() => {
    if (!activeId) return;
    refreshMessages(activeId);
    const channel = supabase
      .channel(`messages-${activeId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'messages',
          filter: `thread_id=eq.${activeId}`,
        },
        () => refreshMessages(activeId)
      )
      .subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
  }, [activeId, refreshMessages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!activeId || !draft.trim()) return;
    setSending(true);
    try {
      await sendThreadMessage(activeId, draft.trim());
      setDraft('');
      await refreshMessages(activeId);
    } finally {
      setSending(false);
    }
  }

  const canReply = role === 'tenant' || role === 'vendor';
  const active = threads.find((t) => t.id === activeId);

  if (loading) return <TableSkeleton rows={6} />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Messages</h1>
        <p className="text-sm text-gray-500 mt-1">
          {role === 'tenant'
            ? 'Agent outreach and vendor replies on your maintenance requests.'
            : 'Job inquiries from EstateFlow — reply with your availability within 24 hours.'}
        </p>
      </div>

      {threads.length === 0 ? (
        <EmptyState
          icon={<MessageSquare className="text-gray-300" size={40} />}
          title="No conversations yet"
          description="Messages appear after a maintenance request is matched to vendors."
        />
      ) : (
        <div className="grid lg:grid-cols-3 gap-4 min-h-[480px]">
          <div className="lg:col-span-1 bg-white rounded-xl border border-gray-200 overflow-hidden">
            <ul className="divide-y divide-gray-100 max-h-[520px] overflow-y-auto">
              {threads.map((t) => {
                const mr = t.maintenance_request;
                const label = mr
                  ? `${mr.ticket_id ?? 'Request'} — ${mr.property_name}`
                  : 'Maintenance thread';
                return (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => setActiveId(t.id)}
                      className={`w-full text-left px-4 py-3 text-sm hover:bg-gray-50 ${
                        activeId === t.id ? 'bg-teal-50 border-l-4 border-teal-600' : ''
                      }`}
                    >
                      <p className="font-medium text-gray-900 truncate">{label}</p>
                      <p className="text-xs text-gray-500 capitalize">{t.status}</p>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 flex flex-col">
            {active ? (
              <>
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="font-semibold text-gray-900 text-sm">
                    {active.maintenance_request?.ticket_id ?? 'Conversation'}
                  </p>
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[400px]">
                  {messages.map((m) => (
                    <div
                      key={m.id}
                      className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                        m.sender_type === 'agent'
                          ? 'bg-amber-50 text-amber-900 mr-auto'
                          : m.sender_type === 'tenant'
                            ? 'bg-teal-700 text-white ml-auto'
                            : 'bg-gray-100 text-gray-900 mr-auto'
                      }`}
                    >
                      <p className="text-[10px] uppercase opacity-70 mb-0.5">
                        {m.sender_type}
                      </p>
                      <p className="whitespace-pre-wrap">{m.body}</p>
                    </div>
                  ))}
                </div>
                {canReply && (
                  <form onSubmit={handleSend} className="p-3 border-t border-gray-100 flex gap-2">
                    <input
                      className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                      placeholder={
                        role === 'vendor'
                          ? 'e.g. Tuesday 2pm works, or: not available this week'
                          : 'Message vendor (optional)'
                      }
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                    />
                    <button
                      type="submit"
                      disabled={sending || !draft.trim()}
                      className="bg-teal-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-1"
                    >
                      <Send size={16} />
                      Send
                    </button>
                  </form>
                )}
              </>
            ) : (
              <p className="p-6 text-sm text-gray-500">Select a conversation</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
