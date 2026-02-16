import React from 'react';
import { MessageSquare, Image as ImageIcon, Plus } from 'lucide-react';

export default function BottomNav({ activeView, onNavigate }) {
    return (
        <div className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 pb-safe">
            <div className="flex justify-around items-center px-2 py-3">
                <button
                    onClick={() => onNavigate('album')}
                    className={`flex flex-col items-center space-y-1 p-2 ${activeView === 'album' ? 'text-sky-600' : 'text-slate-500'
                        }`}
                >
                    <ImageIcon size={24} />
                    <span className="text-xs font-medium">Album</span>
                </button>

                <button className="bg-sky-500 text-white p-3 rounded-full -mt-8 shadow-lg ring-4 ring-white">
                    <Plus size={24} />
                </button>

                <button
                    onClick={() => onNavigate('chat')}
                    className={`flex flex-col items-center space-y-1 p-2 ${activeView === 'chat' ? 'text-sky-600' : 'text-slate-500'
                        }`}
                >
                    <MessageSquare size={24} />
                    <span className="text-xs font-medium">Chat</span>
                </button>
            </div>
        </div>
    );
}
