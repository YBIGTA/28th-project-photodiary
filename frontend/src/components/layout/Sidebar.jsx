import React from 'react';
import { MessageSquare, Image as ImageIcon, Plus, BookOpen } from 'lucide-react';
import logo from '../../assets/logo.png';

export default function Sidebar({ activeView, onNavigate }) {
    return (
        // 화면 왼쪽에 살짝 여백을 둔 둥근 직사각형(알약 모양) 플로팅 웜 카드
        // 사이드바가 튀지 않도록 배경을 얕은 크림색 계열로 설정
        <div className="hidden md:flex flex-col w-20 h-[calc(100vh-16px)] my-2 ml-2 bg-white/70 backdrop-blur-xl border border-white/80 shadow-sm rounded-3xl z-20 items-center py-6">

            {/* 로고 영역 (클릭 시 메인 화면으로 이동) */}
            <div className="mb-8 flex justify-center w-full">
                <button
                    onClick={() => onNavigate('album')}
                    className="focus:outline-none transition-transform duration-300 hover:scale-110"
                    title="Home"
                >
                    <img
                        src={logo}
                        alt="PicTrace"
                        className="w-10 h-10 object-contain drop-shadow-sm"
                    />
                </button>
            </div>

            {/* 내비게이션 메뉴 */}
            <nav className="flex-1 space-y-4 flex flex-col items-center w-full px-3">
                <div className="relative group w-full flex justify-center">
                    <button
                        onClick={() => onNavigate('album')}
                        className={`p-3.5 rounded-2xl w-full flex justify-center transition-all duration-300 ${activeView === 'album'
                            ? 'bg-[#EAE5D9] text-[#B6694E] shadow-sm'
                            : 'text-[#6B6653] hover:bg-[#F2EEE4]/50'
                            }`}
                    >
                        <ImageIcon size={22} strokeWidth={activeView === 'album' ? 2.5 : 2} />
                    </button>
                    {/* 툴팁 */}
                    <span className="absolute left-14 top-1/2 -translate-y-1/2 ml-2 px-2.5 py-1.5 bg-[#6B6653] text-[#FDFBF7] text-xs font-medium rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50 shadow-md flex items-center">
                        Photos
                        <div className="absolute -left-1 w-2 h-2 bg-[#6B6653] rotate-45"></div>
                    </span>
                </div>

                <div className="relative group w-full flex justify-center">
                    <button
                        onClick={() => onNavigate('memories')}
                        className={`p-3.5 rounded-2xl w-full flex justify-center transition-all duration-300 ${activeView === 'memories'
                            ? 'bg-[#EAE5D9] text-[#B6694E] shadow-sm'
                            : 'text-[#6B6653] hover:bg-[#F2EEE4]/50'
                            }`}
                    >
                        <BookOpen size={22} strokeWidth={activeView === 'memories' ? 2.5 : 2} />
                    </button>
                    {/* 툴팁 */}
                    <span className="absolute left-14 top-1/2 -translate-y-1/2 ml-2 px-2.5 py-1.5 bg-[#6B6653] text-[#FDFBF7] text-xs font-medium rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50 shadow-md flex items-center">
                        Memories
                        <div className="absolute -left-1 w-2 h-2 bg-[#6B6653] rotate-45"></div>
                    </span>
                </div>

                <div className="relative group w-full flex justify-center">
                    <button
                        onClick={() => onNavigate('chat')}
                        className={`p-3.5 rounded-2xl w-full flex justify-center transition-all duration-300 ${activeView === 'chat'
                            ? 'bg-[#EAE5D9] text-[#B6694E] shadow-sm'
                            : 'text-[#6B6653] hover:bg-[#F2EEE4]/50'
                            }`}
                    >
                        <MessageSquare size={22} strokeWidth={activeView === 'chat' ? 2.5 : 2} />
                    </button>
                    {/* 툴팁 */}
                    <span className="absolute left-14 top-1/2 -translate-y-1/2 ml-2 px-2.5 py-1.5 bg-[#6B6653] text-[#FDFBF7] text-xs font-medium rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50 shadow-md flex items-center">
                        Chat
                        <div className="absolute -left-1 w-2 h-2 bg-[#6B6653] rotate-45"></div>
                    </span>
                </div>
            </nav>

            {/* 사진 업로드 액션 버튼 (호버 시 위로 확장됨) */}
            <div className="mt-auto px-2 w-full h-[72px] flex justify-center items-end">
                <button
                    className="group w-full flex flex-col items-center justify-end bg-[#D7AD7E] hover:bg-[#c49b6c] text-white rounded-2xl transition-all duration-300 shadow-sm overflow-hidden h-12 hover:h-[72px] pb-[10px]"
                >
                    <span className="text-[10px] uppercase tracking-widest font-bold mb-1 opacity-0 group-hover:opacity-100 transition-all duration-300 translate-y-2 group-hover:translate-y-0 pointer-events-none">
                        Upload
                    </span>
                    <Plus size={24} strokeWidth={3} className="shrink-0" />
                </button>
            </div>
        </div>
    );
}
