'use client';
import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import { api, Device, Event } from '@/lib/api';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';

export default function OverviewPage() {
    const { token } = useAuth();
    const [devices, setDevices] = useState<Device[]>([]);
    const [events, setEvents] = useState<Event[]>([]);
    const [loading, setLoading] = useState(true);

    const loadData = useCallback(() => {
        if (!token) return;
        Promise.all([api.listDevices(token), api.listEvents(token, 0, 10)])
            .then(([d, e]) => { setDevices(d); setEvents(e); })
            .finally(() => setLoading(false));
    }, [token]);

    useEffect(() => {
        loadData();
        const interval = setInterval(loadData, 2000);
        return () => clearInterval(interval);
    }, [loadData]);

    const online = devices.filter(d => d.online).length;
    const armed = devices.filter(d => d.armed).length;
    const total = devices.length;

    if (loading) return <div style={{ color: 'var(--text-muted)', padding: 40 }}>Loading…</div>;

    return (
        <>
            <div className="page-header">
                <h1>Overview</h1>
                <p>Your security system at a glance</p>
            </div>

            {/* Stat cards */}
            <div className="grid-4 mb-4">
                {[
                    { label: 'Total Devices', value: total, color: '#a5b4fc' },
                    { label: 'Online', value: online, color: 'var(--success)' },
                    { label: 'Armed', value: armed, color: 'var(--warning)' },
                    { label: 'Events today', value: events.length, color: '#f9a8d4' },
                ].map(s => (
                    <div className="stat-card" key={s.label}>
                        <div className="label">{s.label}</div>
                        <div className="value" style={{ color: s.color }}>{s.value}</div>
                    </div>
                ))}
            </div>

            {/* Devices quick view */}
            <div className="card mb-4">
                <div className="flex items-center justify-between mb-4">
                    <h2 style={{ fontWeight: 700, fontSize: 15 }}>Devices</h2>
                    <a href="/dashboard/devices" style={{ fontSize: 13, color: '#a5b4fc' }}>View all →</a>
                </div>
                {devices.length === 0 ? (
                    <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                        No devices yet. Go to <a href="/dashboard/devices" style={{ color: '#a5b4fc' }}>Devices</a> to add one.
                    </p>
                ) : (
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Name</th><th>Status</th><th>Armed</th><th>Last seen</th>
                            </tr>
                        </thead>
                        <tbody>
                            {devices.map(d => (
                                <tr key={d.id}>
                                    <td style={{ fontWeight: 600 }}>{d.name || `Device #${d.id}`}</td>
                                    <td>
                                        <span className={`badge ${d.online ? 'badge-green' : 'badge-gray'}`}>
                                            <span className={`dot ${d.online ? 'dot-green' : 'dot-gray'}`} />
                                            {d.online ? 'Online' : 'Offline'}
                                        </span>
                                    </td>
                                    <td>
                                        <span className={`badge ${d.armed ? 'badge-yellow' : 'badge-gray'}`}>
                                            {d.armed ? '🔒 Armed' : '🔓 Disarmed'}
                                        </span>
                                    </td>
                                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                                        {d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : '—'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Recent events */}
            <div className="card">
                <div className="flex items-center justify-between mb-4">
                    <h2 style={{ fontWeight: 700, fontSize: 15 }}>Recent Events</h2>
                    <a href="/dashboard/events" style={{ fontSize: 13, color: '#a5b4fc' }}>View all →</a>
                </div>
                {events.length === 0 ? (
                    <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>No events yet.</p>
                ) : (
                    <table className="table">
                        <thead>
                            <tr><th>Time</th><th>Device</th><th>Confidence</th><th>Snapshot</th></tr>
                        </thead>
                        <tbody>
                            {events.slice(0, 5).map(ev => (
                                <tr key={ev.id}>
                                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                                        {new Date(ev.happened_at).toLocaleString()}
                                    </td>
                                    <td>#{ev.device_id}</td>
                                    <td>
                                        <span className="badge badge-purple">
                                            {Math.round(ev.confidence * 100)}%
                                        </span>
                                    </td>
                                    <td>
                                        {ev.image_filename ? (
                                            <img
                                                src={`${BASE}/media/events/${ev.image_filename}`}
                                                alt="snapshot"
                                                style={{ width: 44, height: 44, borderRadius: 8, objectFit: 'cover' }}
                                            />
                                        ) : '—'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </>
    );
}
