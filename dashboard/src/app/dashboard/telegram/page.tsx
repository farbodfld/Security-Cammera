'use client';
import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';

export default function TelegramPage() {
    const { token } = useAuth();

    // Step 1: Generate OTP (dashboard-side)
    const [otp, setOtp] = useState<string | null>(null);
    const [expiry, setExpiry] = useState<string | null>(null);
    const [genLoading, setGenLoading] = useState(false);

    // Step 2: Verify after user sends OTP to bot
    const [verifyCode, setVerifyCode] = useState('');
    const [verifyResult, setVerifyResult] = useState<string | null>(null);
    const [verifyLoading, setVerifyLoading] = useState(false);

    const [error, setError] = useState('');

    const genOtp = async () => {
        if (!token) return;
        setGenLoading(true);
        setError('');
        try {
            const { otp: o, expires_at } = await api.generateTelegramOtp(token);
            setOtp(o);
            setExpiry(expires_at);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed');
        } finally {
            setGenLoading(false);
        }
    };

    const verifyOtp = async () => {
        if (!token || !verifyCode) return;
        setVerifyLoading(true);
        setError('');
        try {
            const res = await fetch(`${BASE}/telegram/verify-otp`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({ otp_code: verifyCode }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail ?? 'Verification failed');
            setVerifyResult(`✅ Linked! Chat ID: ${data.chat_id}`);
            setOtp(null);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Verification failed');
        } finally {
            setVerifyLoading(false);
        }
    };

    return (
        <>
            <div className="page-header">
                <h1>Telegram Alerts</h1>
                <p>Link your Telegram account to receive real-time push notifications</p>
            </div>

            <div className="grid-2">
                {/* How it works */}
                <div className="card">
                    <h3 style={{ fontWeight: 700, marginBottom: 16 }}>How it works</h3>
                    {[
                        ['1', 'Open Telegram and find your SecureCam bot'],
                        ['2', 'Send /start to the bot — it will reply with a link code'],
                        ['3', 'Enter that code in the field on the right and click Verify'],
                        ["4", "You'll receive alerts when a person is detected"],
                    ].map(([n, t]) => (
                        <div key={n} className="flex gap-3 items-center" style={{ marginBottom: 12 }}>
                            <div style={{
                                width: 26, height: 26, borderRadius: '50%',
                                background: 'var(--brand-glow)', color: '#a5b4fc',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: 12, fontWeight: 700, flexShrink: 0,
                            }}>{n}</div>
                            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{t}</span>
                        </div>
                    ))}

                    <hr className="divider" />

                    <h4 style={{ fontWeight: 700, marginBottom: 8, fontSize: 13 }}>Alternative flow</h4>
                    <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        You can also generate an OTP here and send it to the bot instead.
                    </p>
                    <button className="btn btn-outline btn-sm mt-4" onClick={genOtp} disabled={genLoading}>
                        {genLoading ? 'Generating…' : 'Generate OTP'}
                    </button>
                    {otp && (
                        <div style={{
                            marginTop: 12, fontFamily: 'monospace', fontSize: 24,
                            letterSpacing: 6, color: '#a5b4fc', fontWeight: 700,
                            background: 'var(--bg-surface)', padding: '10px 16px', borderRadius: 8,
                        }}>{otp}</div>
                    )}
                    {expiry && <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                        Expires: {new Date(expiry).toLocaleTimeString()}
                    </p>}
                </div>

                {/* Verify OTP (entered from bot) */}
                <div className="card">
                    <h3 style={{ fontWeight: 700, marginBottom: 8 }}>Link Account</h3>
                    <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>
                        Send <code style={{ background: 'var(--bg-surface)', padding: '2px 6px', borderRadius: 4 }}>/start</code> to
                        the bot, then paste the 6-digit code it gives you below.
                    </p>

                    {error && <div className="alert alert-error">{error}</div>}
                    {verifyResult && <div className="alert alert-success">{verifyResult}</div>}

                    {!verifyResult && (
                        <>
                            <div className="form-group">
                                <label className="form-label">6-Digit Code from Bot</label>
                                <input
                                    className="form-input"
                                    placeholder="123456"
                                    maxLength={6}
                                    value={verifyCode}
                                    onChange={e => setVerifyCode(e.target.value.replace(/\D/g, ''))}
                                    style={{ letterSpacing: 6, fontSize: 20, fontFamily: 'monospace' }}
                                />
                            </div>
                            <button
                                className="btn btn-primary w-full"
                                style={{ justifyContent: 'center' }}
                                onClick={verifyOtp}
                                disabled={verifyLoading || verifyCode.length !== 6}
                            >
                                {verifyLoading ? 'Verifying…' : 'Link Account'}
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Commands reference */}
            <div className="card mt-6">
                <h3 style={{ fontWeight: 700, marginBottom: 16 }}>Telegram Commands</h3>
                <table className="table">
                    <thead>
                        <tr><th>Command</th><th>Description</th></tr>
                    </thead>
                    <tbody>
                        {[
                            ['/start', 'Get a link code from the bot'],
                            ['/devices', 'List all your paired devices with status'],
                            ['/arm', 'Arm your camera (shows menu if multiple devices)'],
                            ['/arm 2', 'Arm device #2 from the /devices list'],
                            ['/disarm', 'Disarm your camera'],
                            ['/disarm 1', 'Disarm device #1'],
                        ].map(([cmd, desc]) => (
                            <tr key={cmd}>
                                <td>
                                    <code style={{ background: 'var(--bg-surface)', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>
                                        {cmd}
                                    </code>
                                </td>
                                <td style={{ fontSize: 13, color: 'var(--text-muted)' }}>{desc}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </>
    );
}
