'use client';
import { useState } from 'react';
import Sidebar from '@/components/Sidebar';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const [sidebarOpen, setSidebarOpen] = useState(false);

    return (
        <div className="app-shell">
            {/* Mobile Header */}
            <header className="mobile-header">
                <div className="flex items-center gap-2">
                    <div style={{
                        width: 24, height: 24,
                        background: 'linear-gradient(135deg, #6c63ff, #8b5cf6)',
                        borderRadius: 6,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
                            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                            <circle cx="12" cy="13" r="4" />
                        </svg>
                    </div>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>SecureCam</span>
                </div>
                <button className="hamburger" onClick={() => setSidebarOpen(true)}>
                    ☰
                </button>
            </header>

            {/* Mobile Overlay */}
            <div 
                className={`mobile-overlay ${sidebarOpen ? 'visible' : ''}`} 
                onClick={() => setSidebarOpen(false)} 
            />

            <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
            
            <main className="main-content">{children}</main>
        </div>
    );
}
