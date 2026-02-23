import React from 'react';
import { MessageSquare, Image as ImageIcon, Plus, BookOpen, User, LogOut } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export default function BottomNav({ activeView, onNavigate, onUploadClick }) {
    const { isLoggedIn, logout, openAuthModal } = useAuth();

    return (
        <div className="md:hidden fixed bottom-6 left-6 right-6 bg-white/80 backdrop-blur-xl border border-white/80 shadow-md rounded-[2rem] z-30 flex items-center justify-around px-4 py-3">
            <div className="relative group flex justify-center w-12 h-12 items-center">
                <button
                    onClick={() => onNavigate('album')}
                    className={`p-3 rounded-2xl transition-all duration-300 w-full h-full flex justify-center items-center ${activeView === 'album'
                        ? 'bg-[#EAE5D9] text-[#B6694E] shadow-sm'
                        : 'text-[#6B6653] hover:bg-[#F2EEE4]/50'
                        }`}
                >
                    <ImageIcon size={22} strokeWidth={activeView === 'album' ? 2.5 : 2} />
                </button>
                {/* 툴팁 */}
                <span className="absolute bottom-full mb-3 px-2.5 py-1.5 bg-[#6B6653] text-[#FDFBF7] text-xs font-medium rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50 shadow-md flex flex-col items-center">
                    Photos
                    <div className="absolute -bottom-1 w-2 h-2 bg-[#6B6653] rotate-45"></div>
                </span>
            </div>

            <div className="relative group flex justify-center w-12 h-12 items-center">
                <button
                    onClick={() => onNavigate('memories')}
                    className={`p-3 rounded-2xl transition-all duration-300 w-full h-full flex justify-center items-center ${activeView === 'memories'
                        ? 'bg-[#EAE5D9] text-[#B6694E] shadow-sm'
                        : 'text-[#6B6653] hover:bg-[#F2EEE4]/50'
                        }`}
                >
                    <BookOpen size={22} strokeWidth={activeView === 'memories' ? 2.5 : 2} />
                </button>
                {/* 툴팁 */}
                <span className="absolute bottom-full mb-3 px-2.5 py-1.5 bg-[#6B6653] text-[#FDFBF7] text-xs font-medium rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50 shadow-md flex flex-col items-center">
                    Memories
                    <div className="absolute -bottom-1 w-2 h-2 bg-[#6B6653] rotate-45"></div>
                </span>
            </div>

            {/* 중앙 업로드 기능 - 위로 확장되는 버튼 */}
            <div className="relative flex justify-center mx-1 w-12 h-12">
                <button
                    onClick={onUploadClick}
                    className="absolute bottom-0 group bg-[#D7AD7E] hover:bg-[#c49b6c] text-white w-full rounded-2xl shadow-sm transition-all duration-300 overflow-hidden flex flex-col items-center justify-end h-12 hover:h-[72px] pb-[10px] z-40"
                >
                    <span className="text-[10px] uppercase tracking-normal font-bold mb-1 opacity-0 group-hover:opacity-100 transition-all duration-300 translate-y-2 group-hover:translate-y-0 pointer-events-none">
                        Upload
                    </span>
                    <Plus size={24} strokeWidth={3} className="shrink-0" />
                </button>
            </div>

            <div className="relative group flex justify-center w-12 h-12 items-center">
                <button
                    onClick={() => onNavigate('chat')}
                    className={`p-3 rounded-2xl transition-all duration-300 w-full h-full flex justify-center items-center ${activeView === 'chat'
                        ? 'bg-[#EAE5D9] text-[#B6694E] shadow-sm'
                        : 'text-[#6B6653] hover:bg-[#F2EEE4]/50'
                        }`}
                >
                    <MessageSquare size={22} strokeWidth={activeView === 'chat' ? 2.5 : 2} />
                </button>
                {/* 툴팁 */}
                <span className="absolute bottom-full mb-3 px-2.5 py-1.5 bg-[#6B6653] text-[#FDFBF7] text-xs font-medium rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50 shadow-md flex flex-col items-center">
                    Search/Chat
                    <div className="absolute -bottom-1 w-2 h-2 bg-[#6B6653] rotate-45"></div>
                </span>
            </div>

            <div className="relative group flex justify-center w-12 h-12 items-center">
                <button
                    onClick={isLoggedIn ? logout : openAuthModal}
                    className={`p-3 rounded-full transition-all duration-300 w-full h-full flex justify-center items-center border border-transparent ${isLoggedIn ? 'text-[#B6694E] bg-white border-[#EAE5D9] shadow-sm hover:shadow-md' : 'text-gray-400 hover:text-[#6B6653] bg-transparent hover:bg-white border-[#EAE5D9] hover:shadow-sm'}`}
                >
                    {isLoggedIn ? <LogOut size={22} strokeWidth={2.5} /> : <User size={22} strokeWidth={2} />}
                </button>
                {/* 툴팁 */}
                <span className="absolute bottom-full mb-3 px-2.5 py-1.5 bg-[#6B6653] text-[#FDFBF7] text-xs font-medium rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50 shadow-md flex flex-col items-center">
                    {isLoggedIn ? 'Logout' : 'Profile'}
                    <div className="absolute -bottom-1 w-2 h-2 bg-[#6B6653] rotate-45"></div>
                </span>
            </div>
        </div>
    );
}
