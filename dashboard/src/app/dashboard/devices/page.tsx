'use client';
import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import { api, Device, ControlMode } from '@/lib/api';

const MODES: ControlMode[] = ['BOTH', 'DASHBOARD_ONLY', 'TELEGRAM_ONLY'];

export default function DevicesPage() {
    const { token } = useAuth();
    const [devices, setDevices] = useState<Device[]>([]);
    const [loading, setLoading] = useState(true);
    const [pairCode, setPairCode] = useState<string | null>(null);
    const [pairExpiry, setPairExpiry] = useState<string | null>(null);
    const [genLoading, setGenLoading] = useState(false);
    const [editing, setEditing] = useState<Device | null>(null);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        if (!token) return;
        const d = await api.listDevices(token);
        setDevices(d);
        setLoading(false);
    }, [token]);

    useEffect(() => {
        load();
        const interval = setInterval(load, 2000);
        return () => clearInterval(interval);
    }, [load]);

    const generatePairCode = async () => {
        if (!token) return;
        setGenLoading(true);
        try {
            const { pair_code, expires_at } = await api.generatePairCode(token);
            setPairCode(pair_code);
            setPairExpiry(expires_at);
        } finally {
            setGenLoading(false);
        }
    };

    const toggleArmed = async (device: Device) => {
        if (!token) return;
        await api.updateDevice(token, device.id, { armed: !device.armed });
        load();
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

    if (loading) return <div style={{ color: 'var(--text-muted)', padding: 40 }}>Loading…</div>;

    return (
        <>
            <div className="page-header flex items-center justify-between">
                <div>
                    <h1>Devices</h1>
                    <p>Manage and control your camera agents</p>
                </div>
                <button className="btn btn-primary" onClick={generatePairCode} disabled={genLoading}>
                    {genLoading ? 'Generating…' : '+ Add Device'}
                </button>
            </div>

            {/* Pair Code Banner */}
            {pairCode && (
                <div className="card mb-4" style={{ borderColor: 'var(--brand)', background: 'rgba(108,99,255,0.05)' }}>
                    <h3 style={{ fontWeight: 700, marginBottom: 8 }}>Pair a New Device</h3>
                    <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
                        Run the agent on your machine with this code. Expires at {pairExpiry ? new Date(pairExpiry.endsWith('Z') ? pairExpiry : pairExpiry + 'Z').toLocaleTimeString() : '—'}.
                    </p>
                    <div style={{
                        fontFamily: 'monospace', fontSize: 28, letterSpacing: 6,
                        padding: '16px 24px', background: 'var(--bg-surface)',
                        borderRadius: 8, display: 'inline-block', color: '#a5b4fc', fontWeight: 700,
                    }}>
                        {pairCode}
                    </div>
                    <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 12 }}>
                        <code style={{ background: 'var(--bg-surface)', padding: '3px 8px', borderRadius: 4 }}>
                            python src/main.py --pair-code {pairCode} --server-url http://&lt;your-server&gt;:8000
                        </code>
                    </p>
                    <button className="btn btn-outline btn-sm mt-4" onClick={() => setPairCode(null)}>Dismiss</button>
                </div>
            )}

            {/* Device list */}
            {devices.length === 0 ? (
                <div className="card" style={{ textAlign: 'center', padding: 48 }}>
                    <div style={{ fontSize: 48, marginBottom: 12 }}>📷</div>
                    <h3 style={{ fontWeight: 700, marginBottom: 8 }}>No devices yet</h3>
                    <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Click "Add Device" to generate a pair code.</p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {devices.map(d => (
                        <div className="card" key={d.id} style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                            {/* Status dot */}
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
                                    <span className="badge badge-purple" style={{ textTransform: 'none' }}>
                                        {d.control_mode}
                                    </span>
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="flex gap-2">
                                <button
                                    className={`btn btn-sm ${d.armed ? 'btn-outline' : 'btn-primary'}`}
                                    onClick={() => toggleArmed(d)}
                                >
                                    {d.armed ? '🔓 Disarm' : '🔒 Arm'}
                                </button>
                                <button className="btn btn-outline btn-sm" onClick={() => setEditing({ ...d })}>
                                    Settings
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Edit Modal */}
            {editing && (
                <div className="modal-overlay" onClick={e => e.target === e.currentTarget && setEditing(null)}>
                    <div className="modal">
                        <h2 className="modal-title">Device Settings</h2>

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
