import { useState } from 'react';
import { NavLink, useNavigate, Outlet } from 'react-router-dom';
import { MessageSquare, LogOut, Menu, X, Building, Calendar } from 'lucide-react';
import { NotificationBell } from './NotificationBell';
import { useAuth } from '../contexts/AuthContext';

const vendorNav = [
  { label: 'Messages', to: '/vendor/messages', icon: <MessageSquare size={18} /> },
  { label: 'Calendar', to: '/vendor/calendar', icon: <Calendar size={18} /> },
];

export function VendorLayout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function handleSignOut() {
    await signOut();
    navigate('/login?role=vendor');
  }

  const NavLinks = () => (
    <>
      {vendorNav.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          onClick={() => setMobileOpen(false)}
          className={({ isActive }) =>
            `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              isActive
                ? 'bg-white/20 text-white'
                : 'text-teal-100 hover:bg-white/10 hover:text-white'
            }`
          }
        >
          {item.icon}
          {item.label}
        </NavLink>
      ))}
    </>
  );

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex">
      <aside className="hidden lg:flex flex-col w-60 bg-slate-800 min-h-screen fixed left-0 top-0 z-30">
        <div className="px-5 py-5 border-b border-slate-700">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-white/10 rounded-lg flex items-center justify-center">
              <Building size={18} className="text-white" />
            </div>
            <div>
              <p className="text-white font-bold text-sm leading-tight">EstateFlow Vendor</p>
              <p className="text-slate-400 text-xs">Contractor portal</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          <NavLinks />
          <NotificationBell />
        </nav>
        <div className="px-3 pb-5 border-t border-slate-700 pt-4">
          <p className="text-xs text-slate-400 px-3 mb-2 truncate">{user?.email}</p>
          <button
            type="button"
            onClick={handleSignOut}
            className="w-full flex items-center gap-2 px-3 py-2 text-slate-300 hover:text-white text-sm rounded-lg hover:bg-white/10"
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>

      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-slate-800 h-14 flex items-center px-4 justify-between">
        <span className="text-white font-bold text-sm">EstateFlow Vendor</span>
        <button type="button" onClick={() => setMobileOpen((v) => !v)} className="text-white p-1">
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-30 flex">
          <div className="w-64 bg-slate-800 flex flex-col pt-14 pb-5">
            <nav className="flex-1 px-3 py-4 space-y-0.5">
              <NavLinks />
              <NotificationBell />
            </nav>
          </div>
          <div className="flex-1 bg-black/40" onClick={() => setMobileOpen(false)} />
        </div>
      )}

      <main className="flex-1 lg:ml-60 pt-14 lg:pt-0 min-h-screen">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
