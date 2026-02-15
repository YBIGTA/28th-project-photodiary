import React from 'react';
import { Search } from 'lucide-react';

export default function AlbumView({ onSearchFocus }) {
    return (
        <div className="h-full flex flex-col bg-slate-50">
            <div className="p-4 bg-white border-b border-slate-200 sticky top-0 z-10">
                <div className="relative">
                    <input
                        type="text"
                        placeholder="앨범 검색..."
                        onFocus={onSearchFocus}
                        className="w-full pl-10 pr-4 py-2 bg-slate-100 rounded-xl outline-none focus:ring-2 focus:ring-sky-200"
                    />
                    <Search className="absolute left-3 top-2.5 text-slate-400" size={18} />
                </div>
            </div>

            <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
                <p className="mb-2">아직 구현되지 않은 기능입니다.</p>
                <p className="text-sm">검색창을 누르면 챗봇으로 이동합니다.</p>
            </div>
        </div>
    );
}
