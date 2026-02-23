import React, { useEffect } from 'react';
import { X, ChevronLeft, ChevronRight, Calendar, MapPin } from 'lucide-react';

export default function Lightbox({ isOpen, onClose, photo, onNext, onPrev, hasNext, hasPrev }) {
    // Prevent scrolling when lightbox is open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }
        return () => {
            document.body.style.overflow = 'unset';
        };
    }, [isOpen]);

    // Handle keyboard navigation
    useEffect(() => {
        if (!isOpen) return;

        const handleKeyDown = (e) => {
            if (e.key === 'Escape') onClose();
            if (e.key === 'ArrowRight' && hasNext) onNext();
            if (e.key === 'ArrowLeft' && hasPrev) onPrev();
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, hasNext, hasPrev, onNext, onPrev, onClose]);

    if (!isOpen || !photo) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md transition-opacity duration-300" onClick={onClose}>
            {/* Close Button */}
            <button
                onClick={onClose}
                className="absolute top-4 right-4 text-white/50 hover:text-white transition-colors p-2 z-50"
            >
                <X size={32} />
            </button>

            {/* Navigation Buttons */}
            {hasPrev && (
                <button
                    onClick={(e) => { e.stopPropagation(); onPrev(); }}
                    className="absolute left-4 top-1/2 -translate-y-1/2 text-white/50 hover:text-white bg-black/20 hover:bg-black/40 rounded-full p-2 transition-all z-50"
                >
                    <ChevronLeft size={40} />
                </button>
            )}

            {hasNext && (
                <button
                    onClick={(e) => { e.stopPropagation(); onNext(); }}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-white/50 hover:text-white bg-black/20 hover:bg-black/40 rounded-full p-2 transition-all z-50"
                >
                    <ChevronRight size={40} />
                </button>
            )}

            {/* Main Content */}
            <div className="flex flex-col items-center justify-center w-full h-full p-4 md:p-10" onClick={(e) => e.stopPropagation()}>
                <div className="relative max-w-7xl max-h-[85vh] flex items-center justify-center">
                    <img
                        src={photo.url}
                        alt={photo.caption || "Photo"}
                        className="max-w-full max-h-[80vh] object-contain rounded-sm shadow-2xl"
                    />
                </div>

                {/* Caption & Metadata */}
                <div className="mt-6 text-center max-w-2xl px-4">
                    {photo.caption && (
                        <p className="text-white text-lg font-medium mb-2">{photo.caption}</p>
                    )}

                    <div className="flex items-center justify-center space-x-4 text-slate-400 text-sm">
                        {photo.taken_at && (
                            <div className="flex items-center space-x-1">
                                <Calendar size={14} />
                                <span>{new Date(photo.taken_at).toLocaleDateString()} {new Date(photo.taken_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            </div>
                        )}
                        {(photo.city || photo.road) && (
                            <div className="flex items-center space-x-1">
                                <MapPin size={14} />
                                <span>{photo.city} {photo.building || photo.road}</span>
                            </div>
                        )}
                    </div>

                    {/* Tags */}
                    {photo.tags && photo.tags.length > 0 && (
                        <div className="flex flex-wrap justify-center gap-2 mt-3">
                            {photo.tags.map((tag, i) => (
                                <span key={i} className="text-xs text-white/80 bg-white/10 px-2 py-1 rounded-full border border-white/10">
                                    #{tag}
                                </span>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
