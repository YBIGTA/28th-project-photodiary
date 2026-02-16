import React, { useState } from 'react';
import Sidebar from './components/layout/Sidebar';
import BottomNav from './components/layout/BottomNav';
import ChatView from './features/chat/ChatView';
import AlbumView from './features/album/AlbumView';

function App() {
  const [activeView, setActiveView] = useState('chat'); // 'chat' | 'album'

  const handleNavigate = (view) => {
    setActiveView(view);
  };

  return (
    <div className="flex w-full h-screen overflow-hidden bg-slate-50">
      {/* Desktop Sidebar */}
      <Sidebar activeView={activeView} onNavigate={handleNavigate} />

      {/* Main Content Area */}
      <main className="flex-1 h-full relative w-full">
        {activeView === 'chat' && <ChatView />}
        {activeView === 'album' && (
          <AlbumView onSearchFocus={() => setActiveView('chat')} />
        )}
      </main>

      {/* Mobile Bottom Nav */}
      <BottomNav activeView={activeView} onNavigate={handleNavigate} />
    </div>
  );
}

export default App;
