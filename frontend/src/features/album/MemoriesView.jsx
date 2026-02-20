import React, { useEffect, useState, useRef } from 'react';
import { api } from '../../api/client';

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
    const dateObj = new Date(evt.photos[0].taken_at);
    const year = dateObj.getFullYear();
    const month = dateObj.getMonth() + 1;
    const title = `${year}년 ${month}월, ${evt.location}`;

    // 모의 설명 텍스트 (추후 파이프라인 LLM 텍스트로 대체)
    const day = dateObj.getDate();
    const description = `${year}년 ${month}월 ${day}일 저녁, ${evt.location}에서 지갑을 잃어버렸지만 다행히 찾았고, 지인 3명과 함께 식사를 하며 즐거운 하루를 보냈다.`;

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

            {/* 텍스트 영역: 좌측 제목(Bold), 우측 설명(자동 줄바꿈 최적화) */}
            <div className="mt-2 p-3 pb-6 md:px-4 md:py-4 bg-slate-50 flex flex-col sm:flex-row justify-between items-start gap-4">
                {/* 좌측 정렬, 줄어들지 않음(shrink-0) */}
                <h3 className="text-xl md:text-2xl font-bold text-slate-800 shrink-0 mt-1">
                    {title}
                </h3>
                {/* 우측 정렬, 자동 줄바꿈. 컨테이너 길이에 따라 좌측 정렬이 될 수도 있으나 우측 여백을 둠 */}
                <p className="text-sm md:text-base text-slate-700 sm:text-right sm:max-w-[65%] break-keep leading-relaxed pt-1">
                    {description}
                </p>
            </div>
        </div>
    );
};

export default function MemoriesView() {
    const [events, setEvents] = useState([]);
    const [photos, setPhotos] = useState([]);

    useEffect(() => {
        // 이벤트와 사진 데이터를 모두 불러옵니다.
        const fetchData = async () => {
            try {
                const allPhotos = await api.getPhotos(100);
                setPhotos(allPhotos);

                // event_id 기준으로 사진을 그룹화합니다.
                const grouped = allPhotos.reduce((acc, photo) => {
                    if (!photo.event_id) return acc;
                    if (!acc[photo.event_id]) {
                        acc[photo.event_id] = {
                            id: photo.event_id,
                            photos: [],
                            date: new Date(photo.taken_at).toLocaleDateString(),
                            location: photo.road || photo.city || '추억의 장소',
                        };
                    }
                    acc[photo.event_id].photos.push(photo);
                    return acc;
                }, {});

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
    }, []);

    return (
        <div className="h-full flex flex-col bg-white overflow-y-auto w-full">
            {/* 상단 패딩 약간 */}
            <div className="p-4 md:p-8">
                {events.length === 0 ? (
                    <div className="text-center text-slate-400 py-20">
                        저장된 추억이 없습니다.
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
            <style jsx>{`
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
