import React, { useState, useRef, useEffect } from 'react';
import { Send, X, Calendar, MapPin } from 'lucide-react';

export default function ChatView() {
    const [messages, setMessages] = useState([
        { id: 1, role: 'assistant', content: '안녕하세요! PicTrace입니다. 어떤 추억을 찾고 계신가요?', photos: [] }
    ]);
    const [input, setInput] = useState('');
    const [showGallery, setShowGallery] = useState(false);
    const [galleryPhotos, setGalleryPhotos] = useState([]);
    const [isTyping, setIsTyping] = useState(false);
    const messagesEndRef = useRef(null);

    // Auto-scroll to bottom
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isTyping]);

    const handleSend = () => {
        if (!input.trim()) return;

        // User message
        const userMsg = { id: Date.now(), role: 'user', content: input };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setIsTyping(true);

        // Simulated AI response
        setTimeout(() => {
            // Mock data for demo
            const mockPhotos = [
                { id: 101, url: 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4', tags: ['Restaurant', 'Pasta', 'Friends'] },
                { id: 102, url: 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5', tags: ['Food', 'Dinner'] },
                { id: 103, url: 'https://images.unsplash.com/photo-1529333166437-7750a6dd5a70', tags: ['Party', 'Wine'] }
            ];

            const aiMsg = {
                id: Date.now() + 1,
                role: 'assistant',
                content: '지난달 합정에서 친구들과 파스타를 먹었던 기록이 있습니다.',
                photos: mockPhotos
            };

            setMessages(prev => [...prev, aiMsg]);
            setGalleryPhotos(mockPhotos);
            setShowGallery(true); // Open gallery when photos are returned
            setIsTyping(false);
        }, 1500);
    };

    return (
        <div className="flex flex-col h-full relative">
            {/* Gallery View (Top 1/2 on PC/Mobile as per spec, but responsive) */}
            <div
                className={`bg-slate-900 transition-all duration-300 ease-in-out border-b border-slate-700 overflow-hidden ${showGallery ? 'h-[40vh] md:h-[50vh] opacity-100' : 'h-0 opacity-0'
                    }`}
            >
                <div className="h-full flex flex-col">
                    <div className="flex justify-between items-center px-4 py-2 bg-slate-800 text-white">
                        <h3 className="text-sm font-medium text-sky-400">검색된 추억 갤러리</h3>
                        <button onClick={() => setShowGallery(false)} className="text-slate-400 hover:text-white">
                            <X size={18} />
                        </button>
                    </div>

                    {/* Horizontal Scroll Gallery */}
                    <div className="flex-1 overflow-x-auto p-4 flex items-center space-x-4">
                        {galleryPhotos.map(photo => (
                            <div key={photo.id} className="relative group shrink-0 h-full aspect-[4/5] md:aspect-video rounded-lg overflow-hidden cursor-pointer">
                                <img src={photo.url} alt="memory" className="w-full h-full object-cover transition-transform group-hover:scale-105" />
                                <div className="absolute inset-x-0 bottom-0 bg-black/60 p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <div className="flex flex-wrap gap-1">
                                        {photo.tags.map((tag, i) => (
                                            <span key={i} className="text-xs text-white bg-sky-600/50 px-1.5 py-0.5 rounded">{tag}</span>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
                {messages.map(msg => (
                    <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div
                            className={`max-w-[80%] md:max-w-[60%] rounded-2xl px-4 py-3 shadow-sm ${msg.role === 'user'
                                    ? 'bg-sky-500 text-white rounded-br-none'
                                    : 'bg-white text-slate-800 border border-slate-100 rounded-bl-none'
                                }`}
                        >
                            <p className="whitespace-pre-wrap">{msg.content}</p>

                            {/* If message has photos, show a small preview grid or button to re-open gallery */}
                            {msg.photos && msg.photos.length > 0 && (
                                <div className="mt-3">
                                    <button
                                        onClick={() => {
                                            setGalleryPhotos(msg.photos);
                                            setShowGallery(true);
                                        }}
                                        className="text-xs flex items-center space-x-1 text-sky-600 hover:underline bg-white/50 px-2 py-1 rounded"
                                    >
                                        <ImageIcon size={14} />
                                        <span>사진 보기 ({msg.photos.length}장)</span>
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                ))}

                {isTyping && (
                    <div className="flex justify-start">
                        <div className="bg-white text-slate-500 px-4 py-3 rounded-2xl rounded-bl-none border border-slate-100 text-sm animate-pulse">
                            생성 중...
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="bg-white border-t border-slate-200 p-3 md:p-4 pb-safe">
                <div className="max-w-4xl mx-auto flex items-center space-x-2 bg-slate-100 rounded-full px-4 py-2 focus-within:ring-2 focus-within:ring-sky-200 transition-all">
                    <input
                        type="text"
                        className="flex-1 bg-transparent border-none outline-none text-slate-800 placeholder-slate-400"
                        placeholder="어떤 추억을 찾고 계신가요?"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    />
                    <button
                        onClick={handleSend}
                        disabled={!input.trim()}
                        className={`p-2 rounded-full transition-colors ${input.trim() ? 'bg-sky-500 text-white' : 'bg-slate-300 text-slate-500'
                            }`}
                    >
                        <Send size={18} />
                    </button>
                </div>
            </div>
        </div>
    );
}
