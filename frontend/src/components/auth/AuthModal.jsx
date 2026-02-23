import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { X } from 'lucide-react';

export default function AuthModal() {
    const { isAuthModalOpen, closeAuthModal, login, register } = useAuth();
    const [isLoginView, setIsLoginView] = useState(true);

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [username, setUsername] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    if (!isAuthModalOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        let result;
        if (isLoginView) {
            result = await login(email, password);
        } else {
            result = await register(username, email, password);
        }

        setIsLoading(false);

        if (result.success) {
            closeAuthModal();
            // Reset state
            setEmail('');
            setPassword('');
            setUsername('');
        } else {
            setError(result.error);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={closeAuthModal}>
            <div
                className="bg-[#FDFBF7] rounded-[2rem] w-full max-w-sm overflow-hidden shadow-2xl relative animate-in fade-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Close Button */}
                <button
                    onClick={closeAuthModal}
                    className="absolute top-4 right-4 p-2 text-[#6B6653] hover:bg-[#F2EEE4] rounded-full transition-colors"
                >
                    <X size={20} />
                </button>

                <div className="p-8">
                    <h2 className="text-2xl font-bold text-[#6B6653] mb-6 text-center">
                        {isLoginView ? '로그인' : '회원가입'}
                    </h2>

                    {error && (
                        <div className="mb-4 p-3 bg-red-50 text-red-600 text-sm rounded-xl text-center">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                        {!isLoginView && (
                            <div>
                                <label className="block text-sm font-medium text-[#6B6653] mb-1">아이디</label>
                                <input
                                    type="text"
                                    required
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    className="w-full px-4 py-3 bg-white border border-[#EAE5D9] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#D7AD7E] focus:border-transparent text-[#6B6653]"
                                    placeholder="멋진 이름"
                                />
                            </div>
                        )}
                        <div>
                            <label className="block text-sm font-medium text-[#6B6653] mb-1">이메일</label>
                            <input
                                type="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="w-full px-4 py-3 bg-white border border-[#EAE5D9] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#D7AD7E] focus:border-transparent text-[#6B6653]"
                                placeholder="you@example.com"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-[#6B6653] mb-1">비밀번호</label>
                            <input
                                type="password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-4 py-3 bg-white border border-[#EAE5D9] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#D7AD7E] focus:border-transparent text-[#6B6653]"
                                placeholder="••••••••"
                            />
                        </div>

                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full bg-[#D7AD7E] hover:bg-[#c49b6c] text-white font-medium py-3.5 rounded-xl transition-all shadow-sm mt-2 flex justify-center items-center"
                        >
                            {isLoading ? (
                                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                            ) : (
                                isLoginView ? '로그인' : '회원가입 하기'
                            )}
                        </button>
                    </form>

                    <div className="mt-6 text-center text-sm text-[#6B6653]">
                        {isLoginView ? "아직 계정이 없으신가요? " : "이미 계정이 있으신가요? "}
                        <button
                            onClick={() => {
                                setIsLoginView(!isLoginView);
                                setError('');
                            }}
                            className="font-semibold text-[#B6694E] hover:underline focus:outline-none"
                        >
                            {isLoginView ? '회원가입' : '로그인'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
