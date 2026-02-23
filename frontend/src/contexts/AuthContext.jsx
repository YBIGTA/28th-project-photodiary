import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api/client';

const AuthContext = createContext();

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(null);
    const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

    useEffect(() => {
        // Load token from local storage on mount
        const storedToken = localStorage.getItem('access_token');
        const storedUser = localStorage.getItem('user');

        if (storedToken && storedUser) {
            try {
                setToken(storedToken);
                setUser(JSON.parse(storedUser));
            } catch {
                localStorage.removeItem('access_token');
                localStorage.removeItem('user');
            }
        }
    }, []);

    const login = async (email, password) => {
        try {
            const data = await api.login(email, password);
            setToken(data.access_token);
            setUser({ id: data.user_id, username: data.username, email });
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user', JSON.stringify({ id: data.user_id, username: data.username, email }));
            return { success: true };
        } catch (error) {
            return { success: false, error: error.response?.data?.detail || "로그인에 실패했습니다." };
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
            return { success: false, error: error.response?.data?.detail || "회원가입에 실패했습니다." };
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

export function useAuth() {
    return useContext(AuthContext);
}
