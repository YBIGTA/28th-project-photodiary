import React, { useEffect, useState, useRef, useMemo } from 'react';
import { api } from '../../api/client';
import { Search, ArrowDownUp, Grid } from 'lucide-react';

export default function AlbumView({ onSearchFocus }) {
    const [photos, setPhotos] = useState([]);
    const bottomRef = useRef(null);

    // State for user controls
    const [sortOrder, setSortOrder] = useState('oldest'); // 'oldest', 'newest'
    const [gridCols, setGridCols] = useState(5); // 1, 3, 5, 10

    // Fetch photos
    useEffect(() => {
        api.getPhotos(100).then(data => {
            setPhotos(data);
        }).catch(console.error);
    }, []);

    // Derived sorted photos
    const sortedPhotos = useMemo(() => {
        return [...photos].sort((a, b) => {
            const dateA = new Date(a.taken_at);
            const dateB = new Date(b.taken_at);
            return sortOrder === 'oldest' ? dateA - dateB : dateB - dateA;
        });
    }, [photos, sortOrder]);

    // Auto-scroll to bottom only when initially loading or sorting oldest-to-newest
    useEffect(() => {
        if (sortedPhotos.length > 0 && bottomRef.current && sortOrder === 'oldest') {
            bottomRef.current.scrollIntoView({ behavior: 'auto' });
        }
    }, [sortedPhotos, sortOrder]);

    const handleSortToggle = () => {
        setSortOrder(prev => prev === 'oldest' ? 'newest' : 'oldest');
    };

    const handleGridChange = (cols) => {
        setGridCols(cols);
    };

    const gridClassMap = {
        1: 'grid-cols-1',
        3: 'grid-cols-3',
        5: 'grid-cols-5',
        10: 'grid-cols-10'
    };

    return (
        <div className="h-full flex flex-col bg-transparent relative">
            {/* Sticky Header with Controls */}
            <div className="p-4 bg-[#FDFBF7]/80 backdrop-blur-md border-b border-black/5 sticky top-0 z-10 flex flex-col sm:flex-row gap-4 justify-between items-center w-full">

                {/* Search Bar */}
                <div className="relative w-full max-w-sm">
                    <input
                        type="text"
                        placeholder="앨범 또는 사진 검색..."
                        onFocus={onSearchFocus}
                        className="w-full pl-10 pr-4 py-2 bg-slate-100 rounded-xl outline-none focus:ring-2 focus:ring-sky-200 transition-shadow text-sm"
                    />
                    <Search className="absolute left-3 top-2.5 text-slate-400" size={18} />
                </div>

                {/* View Controls */}
                <div className="flex items-center space-x-4">
                    {/* Sort Toggle */}
                    <button
                        onClick={handleSortToggle}
                        className="flex items-center space-x-1 px-3 py-1.5 bg-white border border-[#EAE5D9] rounded-lg text-sm font-medium text-[#6B6653] hover:bg-[#F2EEE4]/50 transition-colors shadow-sm"
                    >
                        <ArrowDownUp size={14} />
                        <span>{sortOrder === 'oldest' ? 'Oldest' : 'Newest'}</span>
                    </button>

                    {/* Grid Size Selectors */}
                    <div className="flex items-center space-x-1 bg-white border border-[#EAE5D9] rounded-lg p-1 shadow-sm">
                        <Grid size={14} className="text-[#6B6653] ml-1 mr-2" />
                        {[1, 3, 5, 10].map(cols => (
                            <button
                                key={cols}
                                onClick={() => handleGridChange(cols)}
                                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${gridCols === cols
                                    ? 'bg-[#EAE5D9] text-[#B6694E] shadow-sm'
                                    : 'text-[#6B6653] hover:bg-[#F2EEE4]/50'
                                    }`}
                            >
                                {cols}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Photo Grid Area */}
            <div className="flex-1 overflow-y-auto w-full">
                {/* Grid container with dynamic columns */}
                <div className={`grid ${gridClassMap[gridCols]} gap-[2px] p-[2px] bg-slate-100 w-full mb-8`}>
                    {sortedPhotos.map((photo) => (
                        <div
                            key={photo.id}
                            className="relative aspect-square bg-slate-200 overflow-hidden flex items-center justify-center group cursor-pointer"
                        >
                            <img
                                src={photo.url}
                                alt={photo.caption || "Photo"}
                                className="w-full h-full object-cover"
                                loading="lazy"
                            />
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

