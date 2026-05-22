import { useState, FormEvent, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Building, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../lib/supabase';
import { UserRole } from '../types';

type SignInRole = UserRole;

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: Location })?.from?.pathname ?? '/';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [signInRole, setSignInRole] = useState<SignInRole>('tenant');
  const [signUpRole, setSignUpRole] = useState<'tenant' | 'manager' | 'inspector' | 'admin'>('tenant');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get('role') === 'vendor') setSignInRole('vendor');
  }, [location.search]);

  async function handleSignIn(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signIn(email, password, signInRole);
      navigate(signInRole === 'vendor' ? '/vendor/messages' : from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  async function handleSignUp(e: FormEvent) {
    e.preventDefault();
    if (!fullName.trim()) {
      setError('Full name is required.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const { error: signUpErr } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: { full_name: fullName, role: signUpRole },
          emailRedirectTo: `${window.location.origin}/`,
        },
      });
      if (signUpErr) throw signUpErr;

      const { error: roleErr } = await supabase.auth.updateUser({
        data: { role: signUpRole },
      });
      if (roleErr) throw roleErr;

      setEmail('');
      setPassword('');
      setFullName('');
      setIsSignUp(false);
      alert('Sign-up successful! Please sign in with your credentials.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-up failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  const vendorSignIn = !isSignUp && signInRole === 'vendor';

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-teal-700 rounded-xl flex items-center justify-center mb-4 shadow-card-md">
            <Building size={24} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">EstateFlow</h1>
          <p className="text-sm text-gray-500 mt-1">AI-powered property management</p>
        </div>

        <div className="bg-white rounded-xl shadow-card-md border border-gray-100 p-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">
            {isSignUp ? 'Create account' : 'Sign in'}
          </h2>
          <p className="text-sm text-gray-500 mb-6">
            {isSignUp
              ? 'Join EstateFlow (tenant, manager, or inspector)'
              : vendorSignIn
                ? 'Vendor sign-in uses your EstateFlow contractor account'
                : 'Enter your credentials to continue'}
          </p>

          {error && (
            <div className="flex items-start gap-2.5 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5 mb-5">
              <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={isSignUp ? handleSignUp : handleSignIn} className="space-y-4">
            {isSignUp && (
              <div>
                <label htmlFor="fullName" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Full name
                </label>
                <input
                  id="fullName"
                  type="text"
                  autoComplete="name"
                  required={isSignUp}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Your full name"
                  className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all placeholder-gray-400"
                />
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1.5">
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all placeholder-gray-400"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete={isSignUp ? 'new-password' : 'current-password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3 py-2.5 pr-10 text-sm border border-gray-200 rounded-lg outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all placeholder-gray-400"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {!isSignUp && (
              <div>
                <label htmlFor="signInRole" className="block text-sm font-medium text-gray-700 mb-1.5">
                  I am signing in as…
                </label>
                <select
                  id="signInRole"
                  value={signInRole}
                  onChange={(e) => setSignInRole(e.target.value as SignInRole)}
                  className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all bg-white"
                >
                  <option value="tenant">Tenant</option>
                  <option value="manager">Property Manager</option>
                  <option value="inspector">Inspector</option>
                  <option value="admin">Administrator</option>
                  <option value="vendor">Vendor / Contractor</option>
                </select>
              </div>
            )}

            {isSignUp && (
              <div>
                <label htmlFor="signUpRole" className="block text-sm font-medium text-gray-700 mb-1.5">
                  I am a…
                </label>
                <select
                  id="signUpRole"
                  value={signUpRole}
                  onChange={(e) => setSignUpRole(e.target.value as typeof signUpRole)}
                  className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all bg-white"
                >
                  <option value="tenant">Tenant</option>
                  <option value="manager">Property Manager</option>
                  <option value="inspector">Inspector</option>
                  <option value="admin">Administrator</option>
                </select>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-teal-700 hover:bg-teal-800 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium py-2.5 px-4 rounded-lg transition-colors text-sm flex items-center justify-center gap-2"
            >
              {loading && (
                <div className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin" />
              )}
              {loading
                ? isSignUp
                  ? 'Creating account…'
                  : 'Signing in…'
                : isSignUp
                  ? 'Create account'
                  : 'Sign in'}
            </button>
          </form>

          {!isSignUp && signInRole === 'vendor' && (
            <p className="text-center text-sm text-gray-500 mt-4">
              New contractor?{' '}
              <Link to="/vendor/register" className="text-teal-700 font-medium hover:underline">
                Register as a vendor
              </Link>
            </p>
          )}

          <p className="text-center text-sm text-gray-500 mt-4">
            {isSignUp ? 'Already have an account? ' : "Don't have an account? "}
            <button
              type="button"
              onClick={() => {
                setIsSignUp(!isSignUp);
                setError('');
              }}
              className="text-teal-700 hover:text-teal-800 font-medium transition-colors"
            >
              {isSignUp ? 'Sign in' : signInRole === 'vendor' ? 'Back to sign in' : 'Create one'}
            </button>
          </p>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          EstateFlow &copy; {new Date().getFullYear()} — Pakistan
        </p>
      </div>
    </div>
  );
}
