import React, { useEffect, useState, useRef } from 'react';
import { api } from '../../api/client';
import { Search } from 'lucide-react';

export default function AlbumView({ onSearchFocus }) {
    const [photos, setPhotos] = useState([]);
    const bottomRef = useRef(null);

    // Fetch and sort photos (oldest to newest)
    useEffect(() => {
        api.getPhotos(100).then(data => {
            const sorted = data.sort((a, b) => new Date(a.taken_at) - new Date(b.taken_at));
            setPhotos(sorted);
        }).catch(console.error);
    }, []);

    // Auto-scroll to bottom when photos are loaded
    useEffect(() => {
        if (photos.length > 0 && bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: 'auto' });
        }
    }, [photos]);

    return (
        <div className="h-full flex flex-col bg-slate-50 relative">
            {/* Sticky Search Bar Header */}
            <div className="p-4 bg-white/80 backdrop-blur-md border-b border-slate-200 sticky top-0 z-10">
                <div className="relative max-w-2xl mx-auto">
                    <input
                        type="text"
                        placeholder="앨범 또는 사진 검색..."
                        onFocus={onSearchFocus}
                        className="w-full pl-10 pr-4 py-2 bg-slate-100 rounded-xl outline-none focus:ring-2 focus:ring-sky-200 transition-shadow"
                    />
                    <Search className="absolute left-3 top-2.5 text-slate-400" size={18} />
                </div>
            </div>

            {/* Photo Grid Area */}
            <div className="flex-1 overflow-y-auto w-full">
                {/* 
                  Strict 5 columns layout. 
                  gap-[2px] and p-[2px] mimic the tight spacing of Apple Photos.
                */}
                <div className="grid grid-cols-5 gap-[2px] p-[2px] bg-slate-100 w-full mb-8">
                    {photos.map((photo) => (
                        <div
                            key={photo.id}
                            className="relative aspect-square bg-slate-200 overflow-hidden flex items-center justify-center group cursor-pointer"
                        >
                            {/* 
                                object-contain ensures the whole image fits securely inside the square container 
                                without altering its aspect ratio. 
                            */}
                            <img
                                src={photo.url}
                                alt={photo.caption || "Photo"}
                                className="w-full h-full object-contain"
                                loading="lazy"
                            />

                            {/* Optional: Hover overlay for future features (e.g. selection) */}
                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors pointer-events-none" />
                        </div>
                    ))}
                </div>

                {/* Element to scroll to */}
                <div ref={bottomRef} className="h-4 w-full" />
            </div>
        </div>
    );
}

