'use client';
import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';

// ── Download links driven by env vars — set in dashboard/.env.local ──────────
// NEXT_PUBLIC_DL_WINDOWS / NEXT_PUBLIC_DL_MACOS / NEXT_PUBLIC_DL_LINUX
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
  { n: 1, title: 'Download',    icon: '⬇️' },
  { n: 2, title: 'Open App',    icon: '🖥️' },
  { n: 3, title: 'Enter Code',  icon: '🔑' },
  { n: 4, title: 'Done!',       icon: '✅' },
];

export default function SetupPage() {
  const { token } = useAuth();
  const [step,       setStep]       = useState(1);
  const [pairCode,   setPairCode]   = useState('');
  const [expiresAt,  setExpiresAt]  = useState<Date | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError,   setGenError]   = useState('');

  // Countdown timer
  const [secondsLeft, setSecondsLeft] = useState(0);
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

  const generateCode = useCallback(async () => {
    if (!token) return;
    setGenerating(true);
    setGenError('');
    try {
      const data = await api.generatePairCode(token);
      setPairCode(data.pair_code);
      setExpiresAt(new Date(data.expires_at));
      setStep(3);
    } catch (err: unknown) {
      setGenError(err instanceof Error ? err.message : 'Failed to generate code.');
    } finally {
      setGenerating(false);
    }
  }, [token]);

  // ── Styles ──────────────────────────────────────────────────────────────────
  const stepCard = (active: boolean): React.CSSProperties => ({
    flex: 1,
    padding: '12px 8px',
    borderRadius: 12,
    textAlign: 'center',
    background: active ? 'var(--accent, #4f46e5)' : 'var(--surface, #1e1b4b)',
    opacity: active ? 1 : 0.4,
    transition: 'all .3s',
    color: 'white',
  });

  return (
    <div style={{ maxWidth: 680, margin: '0 auto' }}>
      <div className="page-header">
        <h1>Add a Device</h1>
        <p>Follow these steps to connect a new camera device to your account.</p>
      </div>

      {/* ── Step tracker ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 32 }}>
        {STEPS.map(s => (
          <div key={s.n} style={stepCard(step >= s.n)}>
            <div style={{ fontSize: 22 }}>{s.icon}</div>
            <div style={{ fontSize: 10, marginTop: 4, opacity: 0.8 }}>Step {s.n}</div>
            <div style={{ fontSize: 12, fontWeight: 600, marginTop: 2 }}>{s.title}</div>
          </div>
        ))}
      </div>

      {/* ── Step 1 — Download ─────────────────────────────────────────────── */}
      <div className="card mb-4">
        <h2 style={{ fontWeight: 700, marginBottom: 16, fontSize: 15 }}>
          Step 1 — Download SecuraCam
        </h2>
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
              title={dl.available ? undefined : 'Download link not configured'}
            >
              <span style={{ fontSize: 18 }}>{dl.icon}</span>
              {dl.label}
            </a>
          ))}
        </div>
        {!DL_LINKS.some(d => d.available) && (
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
            ⚠ Download links are not configured yet. Set{' '}
            <code>NEXT_PUBLIC_DL_WINDOWS</code>,{' '}
            <code>NEXT_PUBLIC_DL_MACOS</code>, and{' '}
            <code>NEXT_PUBLIC_DL_LINUX</code> in{' '}
            <code>dashboard/.env.local</code>.
          </p>
        )}
        {step === 1 && (
          <button
            className="btn-primary"
            style={{ marginTop: 8 }}
            onClick={() => setStep(2)}
          >
            I&apos;ve downloaded it →
          </button>
        )}
      </div>

      {/* ── Step 2 — Open App ─────────────────────────────────────────────── */}
      {step >= 2 && (
        <div className="card mb-4">
          <h2 style={{ fontWeight: 700, marginBottom: 10, fontSize: 15 }}>
            Step 2 — Open SecuraCam on your device
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, lineHeight: 1.6 }}>
            Double-click <strong>SecuraCam</strong> to launch it.
            A setup screen will appear asking for a pairing code — keep it open.
          </p>
          {step === 2 && (
            <button
              className="btn-primary"
              style={{ marginTop: 16 }}
              onClick={generateCode}
              disabled={generating}
            >
              {generating ? 'Generating…' : 'Generate Pairing Code →'}
            </button>
          )}
          {genError && (
            <p style={{ color: '#f87171', fontSize: 13, marginTop: 8 }}>{genError}</p>
          )}
        </div>
      )}

      {/* ── Step 3 — Enter Code ───────────────────────────────────────────── */}
      {step >= 3 && pairCode && (
        <div className="card mb-4">
          <h2 style={{ fontWeight: 700, marginBottom: 12, fontSize: 15 }}>
            Step 3 — Enter this code in the SecuraCam app
          </h2>

          <div style={{
            fontSize: 40, fontFamily: 'monospace', fontWeight: 900,
            letterSpacing: 8, color: '#a5b4fc',
            padding: '20px 0 12px',
          }}>
            {pairCode}
          </div>

          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
            {secondsLeft > 0
              ? `⏱  Expires in ${secondsLeft}s — type this into the app and click "Pair Device".`
              : '⚠  This code has expired. Generate a new one below.'}
          </p>

          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <button
              className="btn-secondary"
              onClick={generateCode}
              disabled={generating}
            >
              {generating ? 'Generating…' : '↻ New Code'}
            </button>
            <button
              className="btn-primary"
              onClick={() => setStep(4)}
            >
              Device is paired →
            </button>
          </div>
        </div>
      )}

      {/* ── Step 4 — Done ─────────────────────────────────────────────────── */}
      {step >= 4 && (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <div style={{ fontSize: 56, marginBottom: 16 }}>✅</div>
          <h2 style={{ fontWeight: 700, marginBottom: 8 }}>Device Connected!</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 24 }}>
            Your camera is now monitoring. Detection events will appear on the dashboard.
          </p>
          <a
            href="/dashboard"
            className="btn-primary"
            style={{ display: 'inline-block' }}
          >
            Go to Dashboard →
          </a>
        </div>
      )}
    </div>
  );
}
