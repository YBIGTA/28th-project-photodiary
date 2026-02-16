import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { Search } from 'lucide-react';

export default function AlbumView({ onSearchFocus }) {
    const [lastEvent, setLastEvent] = useState(null);

    useEffect(() => {
        api.getLastEvent().then(setLastEvent).catch(console.error);
    }, []);

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

            <div className="flex-1 overflow-y-auto p-4">
                {lastEvent ? (
                    <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
                        <h2 className="text-xl font-bold text-slate-800 mb-2">최근 기록</h2>
                        <div className="space-y-2 text-slate-600">
                            <p><span className="font-semibold">날짜:</span> {new Date(lastEvent.started_at).toLocaleDateString()}</p>
                            <p><span className="font-semibold">위치:</span> {lastEvent.primary_location || '알 수 없음'}</p>
                            <p><span className="font-semibold">사진:</span> {lastEvent.photo_count}장</p>
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center h-full text-slate-400">
                        <p>저장된 이벤트가 없습니다.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
