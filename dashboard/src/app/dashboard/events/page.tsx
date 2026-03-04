'use client';
import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import { api, Event } from '@/lib/api';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';

export default function EventsPage() {
    const { token } = useAuth();
    const [events, setEvents] = useState<Event[]>([]);
    const [loading, setLoading] = useState(true);
    const [deleting, setDeleting] = useState(false);
    const [expanded, setExpanded] = useState<number | null>(null);

    const load = useCallback(async () => {
        if (!token) return;
        const e = await api.listEvents(token, 0, 100);
        setEvents(e);
        setLoading(false);
    }, [token]);

    useEffect(() => { load(); }, [load]);

    const handleDeleteAll = async () => {
        if (!token) return;
        if (!confirm('Are you sure you want to delete all events and snapshots? This cannot be undone.')) return;
        setDeleting(true);
        try {
            await api.deleteAllEvents(token);
            await load();
        } finally {
            setDeleting(false);
        }
    };

    if (loading) return <div style={{ color: 'var(--text-muted)', padding: 40 }}>Loading…</div>;

    return (
        <>
            <div className="page-header flex items-center justify-between">
                <div>
                    <h1>Events</h1>
                    <p>{events.length} detection{events.length !== 1 ? 's' : ''} recorded</p>
                </div>
                <div className="flex gap-2">
                    <button className="btn btn-outline btn-sm text-error border-error hover:bg-error hover:text-white"
                        onClick={handleDeleteAll} disabled={deleting || events.length === 0}
                        style={{ borderColor: 'var(--error)', color: 'var(--error)' }}>
                        {deleting ? 'Deleting…' : '🗑️ Delete All'}
                    </button>
                    <button className="btn btn-outline btn-sm" onClick={load}>↺ Refresh</button>
                </div>
            </div>

            {events.length === 0 ? (
                <div className="card" style={{ textAlign: 'center', padding: 48 }}>
                    <div style={{ fontSize: 48, marginBottom: 12 }}>⚡</div>
                    <h3 style={{ fontWeight: 700, marginBottom: 8 }}>No events yet</h3>
                    <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Events will appear here when your agent detects a person.</p>
                </div>
            ) : (
                <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Device</th>
                                <th>Confidence</th>
                                <th>Snapshot</th>
                            </tr>
                        </thead>
                        <tbody>
                            {events.map(ev => (
                                <>
                                    <tr key={ev.id} style={{ cursor: 'pointer' }} onClick={() =>
                                        setExpanded(expanded === ev.id ? null : ev.id)
                                    }>
                                        <td>
                                            <div style={{ fontWeight: 600, fontSize: 13 }}>
                                                {new Date(ev.happened_at).toLocaleTimeString()}
                                            </div>
                                            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                                {new Date(ev.happened_at).toLocaleDateString()}
                                            </div>
                                        </td>
                                        <td>
                                            <span className="badge badge-purple">#{ev.device_id}</span>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <div style={{
                                                    width: 48, height: 5, borderRadius: 99,
                                                    background: 'var(--border)', position: 'relative', overflow: 'hidden',
                                                }}>
                                                    <div style={{
                                                        position: 'absolute', inset: 0,
                                                        width: `${Math.round(ev.confidence * 100)}%`,
                                                        background: 'var(--brand)',
                                                    }} />
                                                </div>
                                                <span style={{ fontSize: 12, fontWeight: 600 }}>
                                                    {Math.round(ev.confidence * 100)}%
                                                </span>
                                            </div>
                                        </td>
                                        <td>
                                            {ev.image_filename ? (
                                                <img
                                                    src={`${BASE}/media/events/${ev.image_filename}`}
                                                    alt="snapshot"
                                                    style={{ height: 44, width: 68, borderRadius: 6, objectFit: 'cover' }}
                                                    onError={e => (e.currentTarget.style.display = 'none')}
                                                />
                                            ) : (
                                                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>—</span>
                                            )}
                                        </td>
                                    </tr>

                                    {/* Expanded snapshot row */}
                                    {expanded === ev.id && ev.image_filename && (
                                        <tr key={`exp-${ev.id}`}>
                                            <td colSpan={4} style={{ padding: 16, background: 'var(--bg-surface)' }}>
                                                <img
                                                    src={`${BASE}/media/events/${ev.image_filename}`}
                                                    alt="full snapshot"
                                                    style={{ maxWidth: 480, borderRadius: 8, display: 'block' }}
                                                />
                                                <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                                                    Agent time: {new Date(ev.happened_at).toISOString()} |
                                                    Server time: {new Date(ev.created_at).toISOString()}
                                                </p>
                                            </td>
                                        </tr>
                                    )}
                                </>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </>
    );
}
