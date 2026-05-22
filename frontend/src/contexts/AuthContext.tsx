import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { clearVendorToken, hasVendorToken, setVendorToken } from '../lib/vendorAuth';
import { fetchProfile, loginVendor } from '../services/estateflow';
import { UserProfile, UserRole } from '../types';

interface AuthContextValue {
  session: Session | null;
  user: User | null;
  profile: UserProfile | null;
  role: UserRole;
  loading: boolean;
  isAuthenticated: boolean;
  signIn: (email: string, password: string, role: UserRole) => Promise<void>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadProfile() {
    try {
      const p = await fetchProfile();
      setProfile(p);
    } catch {
      setProfile(null);
    }
  }

  async function loadVendorSession() {
    if (!hasVendorToken()) {
      setProfile(null);
      return;
    }
    await loadProfile();
  }

  useEffect(() => {
    if (hasVendorToken()) {
      loadVendorSession().finally(() => setLoading(false));
      return;
    }

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      if (data.session) {
        loadProfile().finally(() => setLoading(false));
      } else {
        setLoading(false);
      }
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, s) => {
      if (hasVendorToken()) return;
      setSession(s);
      if (s) loadProfile();
      else setProfile(null);
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  async function signIn(email: string, password: string, role: UserRole) {
    if (role === 'vendor') {
      await supabase.auth.signOut();
      clearVendorToken();
      const { access_token, vendor } = await loginVendor(email, password);
      setVendorToken(access_token);
      setSession(null);
      setProfile({
        id: vendor.id,
        email: vendor.email ?? email,
        role: 'vendor',
        full_name: vendor.name,
      });
      return;
    }

    clearVendorToken();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    await loadProfile();
  }

  async function signOut() {
    clearVendorToken();
    setProfile(null);
    await supabase.auth.signOut();
    setSession(null);
  }

  const user = session?.user ?? null;
  const role: UserRole = profile?.role ?? 'tenant';
  const isAuthenticated = Boolean(session) || hasVendorToken();

  return (
    <AuthContext.Provider
      value={{
        session,
        user,
        profile,
        role,
        loading,
        isAuthenticated,
        signIn,
        signOut,
        refreshProfile: loadProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
