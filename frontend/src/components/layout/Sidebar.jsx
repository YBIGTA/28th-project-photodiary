import React from 'react';
import { MessageSquare, Image as ImageIcon, Plus, Menu } from 'lucide-react';

export default function Sidebar({ activeView, onNavigate }) {
    return (
        <div className="hidden md:flex flex-col w-64 h-screen bg-slate-50 border-r border-slate-200">
            {/* Logo Area */}
            <div className="p-6">
                <h1 className="text-2xl font-bold text-sky-600">PicTrace</h1>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-4 space-y-2">
                <button
                    onClick={() => onNavigate('chat')}
                    className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-colors ${activeView === 'chat'
                            ? 'bg-sky-100 text-sky-700'
                            : 'text-slate-600 hover:bg-slate-100'
                        }`}
                >
                    <MessageSquare size={20} />
                    <span className="font-medium">Chat</span>
                </button>

                <button
                    onClick={() => onNavigate('album')}
                    className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-colors ${activeView === 'album'
                            ? 'bg-sky-100 text-sky-700'
                            : 'text-slate-600 hover:bg-slate-100'
                        }`}
                >
                    <ImageIcon size={20} />
                    <span className="font-medium">Album</span>
                </button>
            </nav>

            {/* Action Button */}
            <div className="p-4">
                <button className="w-full flex items-center justify-center space-x-2 bg-sky-500 hover:bg-sky-600 text-white px-4 py-3 rounded-xl transition-colors shadow-sm">
                    <Plus size={20} />
                    <span className="font-medium">Upload Photo</span>
                </button>
            </div>
        </div>
    );
}
