import { useState, FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Building, MapPin, Loader2, AlertCircle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { setVendorToken } from '../lib/vendorAuth';
import { registerVendor } from '../services/estateflow';

const SPECIALTIES = [
  'Plumbing', 'Electrical', 'HVAC', 'Carpentry', 'Painting', 'General',
];

export default function VendorRegister() {
  const navigate = useNavigate();
  const { refreshProfile } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [specialty, setSpecialty] = useState('General');
  const [area, setArea] = useState('');
  const [city, setCity] = useState('');
  const [latitude, setLatitude] = useState<number | null>(null);
  const [longitude, setLongitude] = useState<number | null>(null);
  const [geoLoading, setGeoLoading] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  function useMyLocation() {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported in this browser.');
      return;
    }
    setGeoLoading(true);
    setError('');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatitude(pos.coords.latitude);
        setLongitude(pos.coords.longitude);
        setGeoLoading(false);
      },
      () => {
        setError('Could not get location. Allow location access or enter city/area manually.');
        setGeoLoading(false);
      },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (!phone.trim()) {
      setError('Phone number is required.');
      return;
    }
    setLoading(true);
    try {
      const { access_token } = await registerVendor({
        name: name.trim(),
        email: email.trim(),
        password,
        specialty,
        phone: phone.trim(),
        latitude: latitude ?? undefined,
        longitude: longitude ?? undefined,
        city: city.trim() || undefined,
        area: area.trim() || undefined,
      });
      setVendorToken(access_token);
      await refreshProfile();
      navigate('/vendor/messages', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed.');
    } finally {
      setLoading(false);
    }
  }

  const inputClass =
    'w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all placeholder-gray-400';
  const labelClass = 'block text-sm font-medium text-gray-700 mb-1.5';

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-teal-700 rounded-xl flex items-center justify-center mb-4 shadow-card-md">
            <Building size={24} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">EstateFlow</h1>
          <p className="text-sm text-gray-500 mt-1">Vendor registration</p>
        </div>

        <div className="bg-white rounded-xl shadow-card-md border border-gray-100 p-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Create vendor account</h2>
          <p className="text-sm text-gray-500 mb-6">
            Your details are saved in the vendor directory. You choose your own password.
          </p>

          {error && (
            <div className="flex items-start gap-2.5 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5 mb-5">
              <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className={labelClass}>Business / your name</label>
              <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <label className={labelClass}>Email</label>
              <input
                type="email"
                className={inputClass}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <label className={labelClass}>Password</label>
              <input
                type="password"
                className={inputClass}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                autoComplete="new-password"
              />
            </div>
            <div>
              <label className={labelClass}>Phone</label>
              <input
                className={inputClass}
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="03xx-xxxxxxx"
                required
              />
            </div>
            <div>
              <label className={labelClass}>Specialty</label>
              <select
                className={`${inputClass} bg-white`}
                value={specialty}
                onChange={(e) => setSpecialty(e.target.value)}
              >
                {SPECIALTIES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div className="border border-gray-100 rounded-lg p-4 space-y-3 bg-gray-50">
              <p className="text-sm font-medium text-gray-700">Service location</p>
              <button
                type="button"
                onClick={useMyLocation}
                disabled={geoLoading}
                className="w-full flex items-center justify-center gap-2 bg-teal-700 hover:bg-teal-800 text-white py-2.5 rounded-lg text-sm font-medium disabled:opacity-60 transition-colors"
              >
                {geoLoading ? <Loader2 size={16} className="animate-spin" /> : <MapPin size={16} />}
                Use my current location
              </button>
              {latitude != null && longitude != null && (
                <p className="text-xs text-green-700">
                  Location set: {latitude.toFixed(4)}, {longitude.toFixed(4)}
                </p>
              )}
              <div>
                <label className={labelClass}>City</label>
                <input
                  className={inputClass}
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="e.g. Karachi"
                />
              </div>
              <div>
                <label className={labelClass}>Area / neighborhood</label>
                <input
                  className={inputClass}
                  value={area}
                  onChange={(e) => setArea(e.target.value)}
                  placeholder="e.g. Clifton, DHA Phase 5"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-teal-700 hover:bg-teal-800 disabled:opacity-60 text-white font-medium py-2.5 rounded-lg text-sm flex items-center justify-center gap-2"
            >
              {loading && (
                <div className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin" />
              )}
              {loading ? 'Creating account…' : 'Register as vendor'}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Already registered?{' '}
            <Link to="/login?role=vendor" className="text-teal-700 font-medium hover:underline">
              Sign in
            </Link>
          </p>
          <p className="text-center text-xs text-gray-400 mt-2">
            <Link to="/login" className="hover:underline text-gray-500">
              Tenant / manager login
            </Link>
          </p>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          EstateFlow &copy; {new Date().getFullYear()} — Pakistan
        </p>
      </div>
    </div>
  );
}
