import { useEffect, useState, FormEvent } from 'react';
import { User, Phone, MessageCircle, Save, CheckCircle2, AlertCircle, Lock, Smartphone } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { updateProfile } from '../services/estateflow';

export default function Profile() {
  const { user, profile, refreshProfile } = useAuth();

  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [whatsapp, setWhatsapp] = useState('');
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (profile) {
      setFullName(profile.full_name ?? '');
      setWhatsapp(profile.whatsapp_phone ?? '');
    }
  }, [profile]);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setError('');
    setSuccess(false);
    setSaving(true);
    try {
      await updateProfile({
        full_name: fullName || undefined,
        phone: phone || undefined,
        whatsapp_phone: whatsapp || undefined,
      });
      await refreshProfile();
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save profile.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Profile</h1>
        <p className="text-sm text-gray-500 mt-0.5">Manage your account details and notification preferences.</p>
      </div>

      {/* Account info (read-only) */}
      <div className="bg-white rounded-xl shadow-card border border-gray-100 p-5 space-y-3">
        <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
          <Lock size={14} className="text-gray-400" />
          Account
        </h2>
        <div className="flex items-center gap-3 bg-gray-50 rounded-lg px-4 py-3">
          <div className="w-10 h-10 rounded-full bg-teal-100 flex items-center justify-center flex-shrink-0">
            <span className="text-teal-800 font-bold text-sm">
              {user?.email?.[0]?.toUpperCase() ?? 'U'}
            </span>
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">{profile?.full_name || user?.email}</p>
            <p className="text-xs text-gray-500">{user?.email}</p>
            <span className="inline-block mt-1 text-[10px] font-semibold uppercase tracking-wide bg-teal-100 text-teal-800 px-2 py-0.5 rounded-full">
              {profile?.role}
            </span>
          </div>
        </div>
      </div>

      {/* Editable fields */}
      <form onSubmit={handleSave} className="bg-white rounded-xl shadow-card border border-gray-100 p-5 space-y-5">
        <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
          <User size={14} className="text-gray-400" />
          Personal Details
        </h2>

        {success && (
          <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
            <CheckCircle2 size={15} className="text-green-600" />
            <p className="text-sm text-green-700 font-medium">Profile saved successfully!</p>
          </div>
        )}
        {error && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
            <AlertCircle size={15} className="text-red-500" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1.5" htmlFor="fullName">
            Full Name
          </label>
          <div className="relative">
            <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              id="fullName"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Ali Khan"
              className="w-full pl-9 pr-3 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all"
            />
          </div>
        </div>

        {/* WhatsApp — the main new field */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1.5" htmlFor="whatsapp">
            <span className="flex items-center gap-1.5">
              <MessageCircle size={12} className="text-green-600" />
              WhatsApp Number
              <span className="text-gray-400 font-normal">(for maintenance updates)</span>
            </span>
          </label>
          <div className="relative">
            <Smartphone size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              id="whatsapp"
              type="tel"
              value={whatsapp}
              onChange={(e) => setWhatsapp(e.target.value)}
              placeholder="+92 300 1234567 or 03001234567"
              className="w-full pl-9 pr-3 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all"
            />
          </div>
          <div className="mt-2 flex items-start gap-2 bg-green-50 border border-green-100 rounded-lg px-3 py-2.5">
            <MessageCircle size={14} className="text-green-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-xs font-medium text-green-800">WhatsApp Notifications</p>
              <p className="text-xs text-green-700 mt-0.5">
                You'll receive maintenance updates (confirmation, scheduling, follow-up) directly on WhatsApp.
                Works with any Pakistani number (0300–0399 range).
              </p>
            </div>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1.5" htmlFor="phone">
            <span className="flex items-center gap-1.5">
              <Phone size={12} className="text-gray-400" />
              Phone Number
            </span>
          </label>
          <div className="relative">
            <Phone size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              id="phone"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+92 300 1234567"
              className="w-full pl-9 pr-3 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all"
            />
          </div>
        </div>

        <div className="pt-1">
          <button
            type="submit"
            id="save-profile-btn"
            disabled={saving}
            className="flex items-center gap-2 bg-teal-700 hover:bg-teal-800 disabled:opacity-60 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
          >
            {saving ? (
              <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
            ) : (
              <Save size={15} />
            )}
            {saving ? 'Saving…' : 'Save Profile'}
          </button>
        </div>
      </form>

      {/* Notification info box */}
      <div className="bg-white rounded-xl shadow-card border border-gray-100 p-5 space-y-3">
        <h2 className="text-sm font-semibold text-gray-900">Notification Channels</h2>
        <div className="space-y-2.5">
          <div className="flex items-center gap-3 text-sm">
            <div className="w-2 h-2 rounded-full bg-teal-500 flex-shrink-0" />
            <span className="text-gray-700"><strong>In-app</strong> — always active, see bell icon above</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${profile?.whatsapp_phone ? 'bg-green-500' : 'bg-gray-300'}`} />
            <span className="text-gray-700">
              <strong>WhatsApp</strong> — {profile?.whatsapp_phone ? `active (${profile.whatsapp_phone})` : 'add your number above to activate'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
