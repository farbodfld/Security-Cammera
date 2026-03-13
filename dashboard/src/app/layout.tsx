import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/context/AuthContext';
import Script from 'next/script';

export const metadata: Metadata = {
  title: 'SecureCam Dashboard',
  description: 'Monitor and control your security cameras',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
        <Script 
          src="https://accounts.google.com/gsi/client" 
          strategy="beforeInteractive" 
        />
      </body>
    </html>
  );
}
