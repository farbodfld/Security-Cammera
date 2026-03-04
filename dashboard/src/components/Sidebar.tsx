'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';

const NAV = [
    { href: '/dashboard', label: 'Overview', icon: '◈' },
    { href: '/dashboard/devices', label: 'Devices', icon: '⬡' },
    { href: '/dashboard/events', label: 'Events', icon: '⚡' },
    { href: '/dashboard/telegram', label: 'Telegram', icon: '✈' },
];

export default function Sidebar() {
    const pathname = usePathname();
    const { logout } = useAuth();

    return (
        <aside className="sidebar">
            <div className="sidebar-logo">
                <div style={{
                    width: 30, height: 30,
                    background: 'linear-gradient(135deg, #6c63ff, #8b5cf6)',
                    borderRadius: 8,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
                        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                        <circle cx="12" cy="13" r="4" />
                    </svg>
                </div>
                <span>SecureCam</span>
            </div>

            <nav>
                {NAV.map(item => (
                    <Link
                        key={item.href}
                        href={item.href}
                        className={`nav-link ${pathname === item.href ? 'active' : ''}`}
                    >
                        <span style={{ fontSize: 16 }}>{item.icon}</span>
                        {item.label}
                    </Link>
                ))}
            </nav>

            <div className="sidebar-footer">
                <button className="btn btn-outline btn-sm w-full" onClick={logout}
                    style={{ justifyContent: 'center' }}>
                    Sign Out
                </button>
            </div>
        </aside>
    );
}
