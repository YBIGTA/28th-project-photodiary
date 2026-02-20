import React, { useState } from 'react';
import Sidebar from './components/layout/Sidebar';
import BottomNav from './components/layout/BottomNav';
import ChatView from './features/chat/ChatView';
import AlbumView from './features/album/AlbumView';
import MemoriesView from './features/album/MemoriesView';

function App() {
  // 앱 실행 시 첫 화면을 'album' (앨범 사진 VIEW)으로 설정합니다.
  const [activeView, setActiveView] = useState('album'); // 'chat' | 'album' | 'memories'

  const handleNavigate = (view) => {
    setActiveView(view);
  };

  return (
    <div className="flex w-full h-screen overflow-hidden bg-slate-50">
      {/* PC 사이드바 */}
      <Sidebar activeView={activeView} onNavigate={handleNavigate} />

      {/* 메인 콘텐츠 영역 */}
      <main className="flex-1 h-full relative w-full">
        {activeView === 'chat' && <ChatView />}
        {activeView === 'album' && (
          <AlbumView onSearchFocus={() => setActiveView('chat')} />
        )}
        {activeView === 'memories' && <MemoriesView />}
      </main>

      {/* 모바일 하단 내비게이션 바 */}
      <BottomNav activeView={activeView} onNavigate={handleNavigate} />
    </div>
  );
}

export default App;
