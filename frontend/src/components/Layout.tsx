import { useEffect, useState } from 'react';
import { NavLink, useNavigate, Outlet } from 'react-router-dom';
import {
  LayoutDashboard, Plus, CheckSquare, Building2, Users2,
  ClipboardList, LogOut, Menu, X, ChevronDown, Building, User
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { fetchPendingApprovals } from '../services/estateflow';
import { NotificationBell } from './NotificationPanel';
import { UserRole } from '../types';

interface NavItem {
  label: string;
  to: string;
  icon: React.ReactNode;
  roles: UserRole[];
}

const navItems: NavItem[] = [
  { label: 'Dashboard', to: '/', icon: <LayoutDashboard size={18} />, roles: ['tenant', 'manager', 'inspector', 'admin'] },
  { label: 'New Request', to: '/submit', icon: <Plus size={18} />, roles: ['tenant'] },
  { label: 'Approvals', to: '/approvals', icon: <CheckSquare size={18} />, roles: ['manager', 'admin'] },
  { label: 'Inspections', to: '/inspect', icon: <ClipboardList size={18} />, roles: ['manager', 'inspector', 'admin'] },
  { label: 'Properties', to: '/properties', icon: <Building2 size={18} />, roles: ['tenant', 'manager', 'inspector', 'admin'] },
  { label: 'Vendors', to: '/vendors', icon: <Users2 size={18} />, roles: ['manager', 'inspector', 'admin'] },
  { label: 'Profile', to: '/profile', icon: <User size={18} />, roles: ['tenant', 'manager', 'inspector', 'admin'] },
];

export function Layout() {
  const { user, role, signOut } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [approvalCount, setApprovalCount] = useState(0);

  useEffect(() => {
    if (role !== 'manager' && role !== 'admin') return;
    fetchPendingApprovals()
      .then((list) => setApprovalCount(list.length))
      .catch(() => setApprovalCount(0));
  }, [role]);

  const visibleNav = navItems.filter(item => item.roles.includes(role));

  async function handleSignOut() {
    await signOut();
    navigate('/login');
  }

  const NavLinks = () => (
    <>
      {visibleNav.map(item => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
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
          {item.to === '/approvals' && approvalCount > 0 && (
            <span className="ml-auto text-xs bg-amber-400 text-amber-900 font-bold px-1.5 py-0.5 rounded-full">
              {approvalCount}
            </span>
          )}
        </NavLink>
      ))}
    </>
  );

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-60 bg-teal-700 min-h-screen fixed left-0 top-0 z-30">
        <div className="px-5 py-5 border-b border-teal-600">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
              <Building size={18} className="text-white" />
            </div>
            <div className="flex-1">
              <p className="text-white font-bold text-sm leading-tight">EstateFlow</p>
              <p className="text-teal-200 text-xs capitalize">{role}</p>
            </div>
            <NotificationBell />
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5">
          <NavLinks />
        </nav>

        <div className="px-3 pb-5 border-t border-teal-600 pt-4">
          <div className="relative">
            <button
              onClick={() => setUserMenuOpen(v => !v)}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-teal-100 hover:bg-white/10 hover:text-white transition-colors text-sm"
            >
              <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
                <span className="text-white text-xs font-semibold">
                  {user?.email?.[0]?.toUpperCase() ?? 'U'}
                </span>
              </div>
              <span className="flex-1 text-left truncate text-xs">{user?.email}</span>
              <ChevronDown size={14} />
            </button>
            {userMenuOpen && (
              <div className="absolute bottom-full mb-1 left-0 w-full bg-white rounded-lg shadow-card-md border border-gray-100 overflow-hidden">
                <button
                  onClick={handleSignOut}
                  className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  <LogOut size={16} className="text-gray-400" />
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-teal-700 h-14 flex items-center px-4 justify-between">
        <div className="flex items-center gap-2">
          <Building size={18} className="text-white" />
          <span className="text-white font-bold text-sm">EstateFlow</span>
        </div>
        <div className="flex items-center gap-1">
          <NotificationBell />
          <button
            onClick={() => setMobileOpen((v) => !v)}
            className="text-white p-1"
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-30 flex">
          <div className="w-64 bg-teal-700 flex flex-col pt-14 pb-5">
            <nav className="flex-1 px-3 py-4 space-y-0.5">
              <NavLinks />
            </nav>
            <div className="px-3 border-t border-teal-600 pt-3">
              <button
                onClick={handleSignOut}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-teal-100 hover:text-white text-sm rounded-lg hover:bg-white/10 transition-colors"
              >
                <LogOut size={16} />
                Sign out
              </button>
            </div>
          </div>
          <div className="flex-1 bg-black/40" onClick={() => setMobileOpen(false)} />
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 lg:ml-60 pt-14 lg:pt-0 min-h-screen">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
