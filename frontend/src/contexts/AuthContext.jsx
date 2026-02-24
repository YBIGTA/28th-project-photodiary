import React, { useState } from 'react';
import { api } from '../api/client';
import { AuthContext } from './auth-context';

function loadStoredToken() {
    try {
        return localStorage.getItem('access_token') || null;
    } catch {
        return null;
    }
}

function loadStoredUser() {
    try {
        const raw = localStorage.getItem('user');
        return raw ? JSON.parse(raw) : null;
    } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        return null;
    }
}

export function AuthProvider({ children }) {
    const [user, setUser] = useState(loadStoredUser);
    const [token, setToken] = useState(loadStoredToken);
    const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

    const login = async (email, password) => {
        try {
            const data = await api.login(email, password);
            setToken(data.access_token);
            setUser({ id: data.user_id, username: data.username, email });
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user', JSON.stringify({ id: data.user_id, username: data.username, email }));
            return { success: true };
        } catch (error) {
            let errorMsg = "로그인에 실패했습니다.";
            const detail = error.response?.data?.detail;
            if (detail) {
                errorMsg = Array.isArray(detail) ? detail[0].msg : detail;
            }
            return { success: false, error: errorMsg };
        }
    };

    const register = async (username, email, password) => {
        try {
            const data = await api.register(username, email, password);
            setToken(data.access_token);
            setUser({ id: data.user_id, username: data.username, email });
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user', JSON.stringify({ id: data.user_id, username: data.username, email }));
            return { success: true };
        } catch (error) {
            let errorMsg = "회원가입에 실패했습니다.";
            const detail = error.response?.data?.detail;
            if (detail) {
                errorMsg = Array.isArray(detail) ? detail[0].msg : detail;
            }
            return { success: false, error: errorMsg };
        }
    };

    const logout = () => {
        setToken(null);
        setUser(null);
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
    };

    const openAuthModal = () => setIsAuthModalOpen(true);
    const closeAuthModal = () => setIsAuthModalOpen(false);

    const value = {
        user,
        token,
        isLoggedIn: !!token,
        login,
        register,
        logout,
        isAuthModalOpen,
        openAuthModal,
        closeAuthModal
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}

