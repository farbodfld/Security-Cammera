'use client';
import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@/context/AuthContext';

declare global {
  interface Window {
    google: any;
  }
}

export default function GoogleLoginButton() {
  const { googleLogin } = useAuth();
  const buttonRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    
    if (!clientId) {
      setError('Google Client ID not configured');
      return;
    }

    const initializeGoogle = () => {
      if (!window.google) return;

      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async (response: any) => {
          console.log('Google Auth Response Received:', response);
          try {
            await googleLogin(response.credential);
          } catch (err: any) {
            console.error('Google login failed details:', err);
            setError(`Authentication failed: ${err.message || 'Unknown error'}`);
          }
        },
      });

      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: 'outline',
        size: 'large',
        width: '100%',
        text: 'continue_with',
        shape: 'rectangular',
      });
    };

    // Script is loaded in layout.tsx, but check if it's ready
    if (window.google) {
      initializeGoogle();
    } else {
      // Polling or waiting for script load if needed
      const interval = setInterval(() => {
        if (window.google) {
          initializeGoogle();
          clearInterval(interval);
        }
      }, 100);
      return () => clearInterval(interval);
    }
  }, [googleLogin]);

  return (
    <div style={{ marginTop: 16 }}>
      {error && (
        <div style={{ color: '#ef4444', fontSize: '12px', marginBottom: '8px', textAlign: 'center' }}>
          {error}
        </div>
      )}
      <div ref={buttonRef} />
      
      {!error && (
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          margin: '20px 0', 
          color: 'var(--text-muted)', 
          fontSize: '12px' 
        }}>
          <div style={{ flex: 1, height: '1px', background: 'var(--border-color)', opacity: 0.5 }} />
          <span style={{ padding: '0 10px' }}>OR</span>
          <div style={{ flex: 1, height: '1px', background: 'var(--border-color)', opacity: 0.5 }} />
        </div>
      )}
    </div>
  );
}
