'use client';
import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import { api, Device, ControlMode } from '@/lib/api';

const MODES: ControlMode[] = ['BOTH', 'DASHBOARD_ONLY', 'TELEGRAM_ONLY'];

const DL_LINKS = [
    {
        label: 'Windows (.exe)',
        href: process.env.NEXT_PUBLIC_DL_WINDOWS ?? '#',
        icon: '🪟',
        available: !!process.env.NEXT_PUBLIC_DL_WINDOWS,
    },
    {
        label: 'macOS (.app)',
        href: process.env.NEXT_PUBLIC_DL_MACOS ?? '#',
        icon: '🍎',
        available: !!process.env.NEXT_PUBLIC_DL_MACOS,
    },
    {
        label: 'Linux (AppImage)',
        href: process.env.NEXT_PUBLIC_DL_LINUX ?? '#',
        icon: '🐧',
        available: !!process.env.NEXT_PUBLIC_DL_LINUX,
    },
];

const STEPS = [
    { n: 1, title: 'Download', icon: '⬇️' },
    { n: 2, title: 'Open App', icon: '🖥️' },
    { n: 3, title: 'Enter Code', icon: '🔑' },
    { n: 4, title: 'Done!', icon: '✅' },
];

export default function DevicesPage() {
    const { token } = useAuth();
    const [devices, setDevices] = useState<Device[]>([]);
    const [loading, setLoading] = useState(true);
    
    // Add Device Steps State
    const [showSetup, setShowSetup] = useState(false);
    const [step, setStep] = useState(1);
    const [pairCode, setPairCode] = useState<string | null>(null);
    const [expiresAt, setExpiresAt] = useState<Date | null>(null);
    const [secondsLeft, setSecondsLeft] = useState(0);
    const [genLoading, setGenLoading] = useState(false);
    const [genError, setGenError] = useState('');

    const [editing, setEditing] = useState<Device | null>(null);
    const [saving, setSaving] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        if (!token) return;
        try {
            const d = await api.listDevices(token);
            setDevices(d);
        } catch (e) {
            console.error('Failed to load devices:', e);
        } finally {
            setLoading(false);
        }
    }, [token]);

    useEffect(() => {
        load();
        const interval = setInterval(load, 2000);
        return () => clearInterval(interval);
    }, [load]);

    // Countdown timer for setup
    useEffect(() => {
        if (!expiresAt) return;
        const tick = () => {
            const s = Math.max(0, Math.floor((expiresAt.getTime() - Date.now()) / 1000));
            setSecondsLeft(s);
        };
        tick();
        const id = setInterval(tick, 1000);
        return () => clearInterval(id);
    }, [expiresAt]);

    const startSetup = () => {
        setShowSetup(true);
        setStep(1);
        setPairCode(null);
    };

    const generatePairCode = async () => {
        if (!token) return;
        setGenLoading(true);
        setGenError('');
        try {
            const data = await api.generatePairCode(token);
            setPairCode(data.pair_code);
            setExpiresAt(new Date(data.expires_at));
            setStep(3);
        } catch (e: any) {
            setGenError(e.message || 'Failed to generate code');
        } finally {
            setGenLoading(false);
        }
    };

    const saveEdit = async () => {
        if (!token || !editing) return;
        setSaving(true);
        setError('');
        try {
            await api.updateDevice(token, editing.id, {
                name: editing.name,
                armed: editing.armed,
                control_mode: editing.control_mode,
                snapshot_enabled: editing.snapshot_enabled,
                confidence_threshold: editing.confidence_threshold,
                headless: editing.headless,
            });
            setEditing(null);
            load();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Save failed');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!token || !editing) return;
        if (!confirm(`Are you sure you want to remove "${editing.name || `Device #${editing.id}`}"?`)) return;
        
        setDeleting(true);
        setError('');
        try {
            await api.deleteDevice(token, editing.id);
            setEditing(null);
            load();
        } catch (e: any) {
            setError(e.message || 'Deletion failed');
        } finally {
            setDeleting(false);
        }
    };

    const stepCardStyle = (active: boolean): React.CSSProperties => ({
        flex: 1,
        padding: '12px 8px',
        borderRadius: 12,
        textAlign: 'center',
        background: active ? 'var(--accent, #4f46e5)' : 'var(--surface, #1e1b4b)',
        opacity: active ? 1 : 0.4,
        transition: 'all .3s',
        color: 'white',
    });

    if (loading) return <div style={{ color: 'var(--text-muted)', padding: 40 }}>Loading…</div>;

    return (
        <>
            <div className="page-header flex items-center justify-between">
                <div>
                    <h1>Devices</h1>
                    <p>Manage and control your camera agents</p>
                </div>
                {!showSetup && (
                    <button className="btn btn-primary" onClick={startSetup}>
                        + Add Device
                    </button>
                )}
            </div>

            {/* Step-by-Step Setup UI */}
            {showSetup && (
                <div className="card mb-6" style={{ maxWidth: 680, margin: '0 auto 24px' }}>
                    <div className="flex justify-between items-center mb-6">
                        <h2 style={{ fontWeight: 700, fontSize: 18 }}>Add a New Device</h2>
                        <button className="btn btn-outline btn-sm" onClick={() => setShowSetup(false)}>Cancel</button>
                    </div>

                    {/* Step tracker */}
                    <div style={{ display: 'flex', gap: 8, marginBottom: 32 }}>
                        {STEPS.map(s => (
                            <div key={s.n} style={stepCardStyle(step >= s.n)}>
                                <div style={{ fontSize: 22 }}>{s.icon}</div>
                                <div style={{ fontSize: 10, marginTop: 4, opacity: 0.8 }}>Step {s.n}</div>
                                <div style={{ fontSize: 12, fontWeight: 600, marginTop: 2 }}>{s.title}</div>
                            </div>
                        ))}
                    </div>

                    {/* Step 1 — Download */}
                    {step === 1 && (
                        <div>
                            <h3 style={{ fontWeight: 700, marginBottom: 16, fontSize: 15 }}>Step 1 — Download SecuraCam</h3>
                            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
                                {DL_LINKS.map(dl => (
                                    <a
                                        key={dl.label}
                                        href={dl.available ? dl.href : undefined}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{
                                            display: 'flex', alignItems: 'center', gap: 8,
                                            padding: '10px 18px', borderRadius: 10,
                                            background: 'var(--surface-2, #1e1b4b)',
                                            color: dl.available ? 'var(--text, #e2e8f0)' : 'var(--text-muted, #94a3b8)',
                                            textDecoration: 'none', fontWeight: 600, fontSize: 13,
                                            border: '1px solid var(--border, #312e81)',
                                            cursor: dl.available ? 'pointer' : 'not-allowed',
                                            opacity: dl.available ? 1 : 0.5,
                                        }}
                                    >
                                        <span style={{ fontSize: 18 }}>{dl.icon}</span>
                                        {dl.label}
                                    </a>
                                ))}
                            </div>
                            <button className="btn-primary" onClick={() => setStep(2)}>I&apos;ve downloaded it →</button>
                        </div>
                    )}

                    {/* Step 2 — Open App */}
                    {step === 2 && (
                        <div>
                            <h3 style={{ fontWeight: 700, marginBottom: 10, fontSize: 15 }}>Step 2 — Open SecuraCam</h3>
                            <p style={{ color: 'var(--text-muted)', fontSize: 14, lineHeight: 1.6, marginBottom: 16 }}>
                                Double-click <strong>SecuraCam</strong> to launch it.
                                A setup screen will appear asking for a pairing code.
                            </p>
                            <button className="btn-primary" onClick={generatePairCode} disabled={genLoading}>
                                {genLoading ? 'Generating…' : 'Generate Pairing Code →'}
                            </button>
                            {genError && <p style={{ color: '#f87171', fontSize: 13, marginTop: 8 }}>{genError}</p>}
                        </div>
                    )}

                    {/* Step 3 — Enter Code */}
                    {step === 3 && pairCode && (
                        <div>
                            <h3 style={{ fontWeight: 700, marginBottom: 12, fontSize: 15 }}>Step 3 — Enter this code in the app</h3>
                            <div style={{
                                fontSize: 40, fontFamily: 'monospace', fontWeight: 900,
                                letterSpacing: 8, color: '#a5b4fc', padding: '20px 0 12px',
                            }}>{pairCode}</div>
                            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
                                {secondsLeft > 0
                                    ? `⏱ Expires in ${secondsLeft}s — type this into the app and click "Pair Device".`
                                    : '⚠ This code has expired.'}
                            </p>
                            <div className="flex gap-3">
                                <button className="btn-secondary" onClick={generatePairCode} disabled={genLoading}>↻ New Code</button>
                                <button className="btn-primary" onClick={() => setStep(4)}>Device is paired →</button>
                            </div>
                        </div>
                    )}

                    {/* Step 4 — Done */}
                    {step === 4 && (
                        <div style={{ textAlign: 'center', padding: '24px 0' }}>
                            <div style={{ fontSize: 56, marginBottom: 16 }}>✅</div>
                            <h3 style={{ fontWeight: 700, marginBottom: 8 }}>Device Connected!</h3>
                            <p style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 24 }}>Your camera is now monitoring.</p>
                            <button className="btn-primary" onClick={() => setShowSetup(false)}>Finish</button>
                        </div>
                    )}
                </div>
            )}

            {/* Device list */}
            {devices.length === 0 ? (
                <div className="card" style={{ textAlign: 'center', padding: 48 }}>
                    <div style={{ fontSize: 48, marginBottom: 12 }}>📷</div>
                    <h3 style={{ fontWeight: 700, marginBottom: 8 }}>No devices yet</h3>
                    <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Click "+ Add Device" to connect your first camera.</p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {devices.map(d => (
                        <div className="card" key={d.id} style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                            {/* Status icon */}
                            <div style={{
                                width: 44, height: 44, borderRadius: 10, background: 'var(--bg-surface)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                            }}>
                                <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                                    stroke={d.online ? 'var(--success)' : 'var(--text-muted)'} strokeWidth="2">
                                    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                                    <circle cx="12" cy="13" r="4" />
                                </svg>
                            </div>

                            {/* Info */}
                            <div style={{ flex: 1 }}>
                                <div style={{ fontWeight: 700, marginBottom: 4 }}>{d.name || `Device #${d.id}`}</div>
                                <div className="flex gap-2">
                                    <span className={`badge ${d.online ? 'badge-green' : 'badge-gray'}`}>
                                        <span className={`dot ${d.online ? 'dot-green' : 'dot-gray'}`} />
                                        {d.online ? 'Online' : 'Offline'}
                                    </span>
                                    <span className={`badge ${d.armed ? 'badge-yellow' : 'badge-gray'}`}>
                                        {d.armed ? '🔒 Armed' : '🔓 Disarmed'}
                                    </span>
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="flex gap-2">
                                <button className="btn btn-outline btn-sm" onClick={() => setEditing({ ...d })}>
                                    Settings
                                </button>
                            </div>
                        </div>
                    ))}
                    
                    <div style={{ padding: '12px 20px', borderRadius: 12, border: '1px dashed var(--border-color)', opacity: 0.6 }}>
                         <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0, textAlign: 'center' }}>
                            💡 <strong>Hint:</strong> To stop or quit an active camera agent, press <kbd style={{ background: '#333', padding: '2px 5px', borderRadius: 4, border: '1px solid #555' }}>Q</kbd> on your keyboard while the agent window is focused.
                         </p>
                    </div>
                </div>
            )}

            {/* Edit Modal */}
            {editing && (
                <div className="modal-overlay" onClick={e => e.target === e.currentTarget && setEditing(null)}>
                    <div className="modal">
                        <div className="flex justify-between items-center mb-6">
                            <h2 className="modal-title" style={{ margin: 0 }}>Device Settings</h2>
                            <button 
                                onClick={handleDelete}
                                disabled={deleting}
                                style={{ 
                                    background: 'none', border: 'none', color: '#f87171', 
                                    cursor: 'pointer', fontSize: 12, textDecoration: 'underline' 
                                }}
                            >
                                {deleting ? 'Removing...' : 'Remove Device'}
                            </button>
                        </div>

                        {error && <div className="alert alert-error">{error}</div>}

                        <div className="form-group">
                            <label className="form-label">Device Name</label>
                            <input className="form-input" value={editing.name}
                                onChange={e => setEditing({ ...editing, name: e.target.value })} />
                        </div>

                        <div className="form-group">
                            <label className="form-label">Control Mode</label>
                            <select className="form-input" value={editing.control_mode}
                                onChange={e => setEditing({ ...editing, control_mode: e.target.value as ControlMode })}>
                                {MODES.map(m => <option key={m} value={m}>{m}</option>)}
                            </select>
                        </div>

                        <div className="form-group">
                            <label className="form-label">Confidence Threshold ({Math.round((editing.confidence_threshold ?? 0.5) * 100)}%)</label>
                            <input type="range" min={10} max={95} step={5}
                                value={Math.round((editing.confidence_threshold ?? 0.5) * 100)}
                                onChange={e => setEditing({ ...editing, confidence_threshold: parseInt(e.target.value) / 100 })}
                                style={{ width: '100%', accentColor: 'var(--brand)' }} />
                        </div>

                        <div className="flex items-center justify-between mb-4">
                            <label className="form-label" style={{ margin: 0 }}>Snapshot Upload</label>
                            <label className="toggle">
                                <input type="checkbox" checked={editing.snapshot_enabled}
                                    onChange={e => setEditing({ ...editing, snapshot_enabled: e.target.checked })} />
                                <span className="toggle-slider" />
                            </label>
                        </div>

                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <label className="form-label" style={{ margin: 0 }}>Headless Mode</label>
                                <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0 }}>Hide the camera window when remote starting</p>
                            </div>
                            <label className="toggle">
                                <input type="checkbox" checked={editing.headless}
                                    onChange={e => setEditing({ ...editing, headless: e.target.checked })} />
                                <span className="toggle-slider" />
                            </label>
                        </div>

                        <div className="flex items-center justify-between mb-4">
                            <label className="form-label" style={{ margin: 0 }}>Armed</label>
                            <label className="toggle">
                                <input type="checkbox" checked={editing.armed}
                                    onChange={e => setEditing({ ...editing, armed: e.target.checked })} />
                                <span className="toggle-slider" />
                            </label>
                        </div>

                        <div className="flex gap-2 mt-4">
                            <button className="btn btn-primary" style={{ flex: 1, justifyContent: 'center' }}
                                onClick={saveEdit} disabled={saving}>
                                {saving ? 'Saving…' : 'Save Changes'}
                            </button>
                            <button className="btn btn-outline" onClick={() => setEditing(null)}>Cancel</button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
