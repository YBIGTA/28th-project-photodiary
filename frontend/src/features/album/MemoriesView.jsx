import React, { useEffect, useState, useRef } from 'react';
import { api } from '../../api/client';
import { useAuth } from '../../contexts/useAuth';
import { BookOpen } from 'lucide-react';

// 메모리 박스 컴포넌트: 호버 시 가로 자동 스크롤 기능 및 텍스트 레이아웃
const MemoryBox = ({ evt }) => {
    const scrollRef = useRef(null);
    const [isHovered, setIsHovered] = useState(false);
    const animationRef = useRef(null);

    // 호버 시 가로 자동 스크롤 로직 구현
    useEffect(() => {
        const scrollContainer = scrollRef.current;
        if (!scrollContainer) return;

        const startScrolling = () => {
            // 오른쪽 끝에 도달하면 스크롤 중지
            if (scrollContainer.scrollLeft >= (scrollContainer.scrollWidth - scrollContainer.clientWidth)) {
                return;
            }
            // 스크롤 속도
            scrollContainer.scrollLeft += 1.5;
            animationRef.current = requestAnimationFrame(startScrolling);
        };

        if (isHovered) {
            animationRef.current = requestAnimationFrame(startScrolling);
        } else {
            if (animationRef.current) cancelAnimationFrame(animationRef.current);
        }

        return () => {
            if (animationRef.current) cancelAnimationFrame(animationRef.current);
        };
    }, [isHovered]);

    // 제목 포맷: "{year}년 {month}월, {place}"
    const firstTakenAt = evt.photos[0]?.taken_at;
    const dateObj = firstTakenAt ? new Date(firstTakenAt) : new Date();
    const year = dateObj.getFullYear();
    const month = dateObj.getMonth() + 1;
    const title = `${year}년 ${month}월, ${evt.location}`;


    return (
        <div
            className="mb-12 overflow-hidden bg-white"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            {/* 사진 스크롤 컨테이너 (정사각형 크롭 적용) */}
            <div
                ref={scrollRef}
                className="flex overflow-x-auto space-x-3 hide-scrollbar cursor-pointer"
                style={{ scrollBehavior: 'auto' }}
            >
                {evt.photos.map(photo => (
                    <div
                        key={photo.id}
                        className="shrink-0 w-36 h-36 md:w-52 md:h-52 relative rounded-xl overflow-hidden border border-slate-100"
                    >
                        <img
                            src={photo.url}
                            alt={photo.caption || "추억 사진"}
                            className="w-full h-full object-cover"
                            loading="lazy"
                        />
                    </div>
                ))}
            </div>

            {/* 제목 영역 */}
            <div className="mt-2 px-3 pb-6 md:px-4 md:py-3">
                <h3 className="text-xl md:text-2xl font-bold text-slate-800">
                    {title}
                </h3>
            </div>
        </div>
    );
};

export default function MemoriesView() {
    const { isLoggedIn } = useAuth();
    const [events, setEvents] = useState([]);

    useEffect(() => {
        if (!isLoggedIn) return;

        const fetchData = async () => {
            try {
                const allPhotos = await api.getPhotos(100);

                // event_id 기준으로 사진을 그룹화합니다.
                const grouped = allPhotos.reduce((acc, photo) => {
                    if (!photo.event_id) return acc;
                    if (!acc[photo.event_id]) {
                        acc[photo.event_id] = {
                            id: photo.event_id,
                            photos: [],
                            date: new Date(photo.taken_at).toLocaleDateString(),
                            location: null,
                        };
                    }
                    // 장소 정보가 아직 없으면 현재 사진에서 채운다
                    if (!acc[photo.event_id].location) {
                        const loc = photo.road || photo.city;
                        if (loc) acc[photo.event_id].location = loc;
                    }
                    acc[photo.event_id].photos.push(photo);
                    return acc;
                }, {});
                // 장소 정보가 없는 이벤트에 기본값 적용
                Object.values(grouped).forEach(evt => {
                    if (!evt.location) evt.location = '추억의 장소';
                });

                // 최신순으로 정렬합니다.
                const eventArray = Object.values(grouped).sort((a, b) => {
                    return new Date(b.photos[0].taken_at) - new Date(a.photos[0].taken_at);
                });

                setEvents(eventArray);
            } catch (error) {
                console.error("추억 데이터를 불러오는데 실패했습니다.", error);
            }
        };

        fetchData();
    }, [isLoggedIn]);

    return (
        <div className="h-full flex flex-col bg-transparent overflow-y-auto w-full">
            {/* 상단 패딩 약간 */}
            <div className="p-4 md:p-8 flex-1 flex flex-col">
                {events.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-slate-400 min-h-[50vh] space-y-3">
                        <div className="w-16 h-16 bg-[#F2EEE4] text-[#D7AD7E] rounded-full flex items-center justify-center mb-2">
                            <BookOpen size={32} />
                        </div>
                        <h3 className="text-xl font-bold text-[#6B6653]">{isLoggedIn ? '빈 갤러리' : '로그인이 필요합니다'}</h3>
                        <p className="text-[#6B6653]/70 font-medium">{isLoggedIn ? '사진을 업로드해 보세요!' : '로그인하여 사진을 업로드해 보세요.'}</p>
                    </div>
                ) : (
                    <div className="max-w-7xl mx-auto w-full">
                        {events.map((evt) => (
                            <MemoryBox key={evt.id} evt={evt} />
                        ))}
                    </div>
                )}
            </div>

            {/* 가로 스크롤바 숨기기 전역 설정 */}
            <style>{`
                .hide-scrollbar::-webkit-scrollbar {
                    display: none;
                }
                .hide-scrollbar {
                    -ms-overflow-style: none;
                    scrollbar-width: none;
                }
            `}</style>
        </div>
    );
}
