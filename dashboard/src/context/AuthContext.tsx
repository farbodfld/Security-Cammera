'use client';
import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { api, TokenResponse } from '@/lib/api';
import { useRouter } from 'next/navigation';

interface AuthCtx {
    token: string | null;
    login: (email: string, password: string) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthCtx>({
    token: null,
    login: async () => { },
    logout: () => { },
});

export function AuthProvider({ children }: { children: ReactNode }) {
    const [token, setToken] = useState<string | null>(null);
    const router = useRouter();

    useEffect(() => {
        const t = localStorage.getItem('token');
        if (t) setToken(t);
    }, []);

    const login = async (email: string, password: string) => {
        const { access_token }: TokenResponse = await api.login(email, password);
        setToken(access_token);
        localStorage.setItem('token', access_token);
        router.push('/dashboard');
    };

    const logout = () => {
        setToken(null);
        localStorage.removeItem('token');
        router.push('/login');
    };

    return (
        <AuthContext.Provider value={{ token, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
