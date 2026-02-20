export const MOCK_EVENTS = [
    {
        id: 'evt_001',
        started_at: '2024-02-10T11:30:00',
        ended_at: '2024-02-10T14:30:00',
        primary_location: '서울 마포구 연남동',
        photo_count: 12,
        summary: '친구들과 연남동 브런치 카페에서 식사 후 경의선 숲길 산책',
        cover_photo_id: 'photo_001'
    },
    {
        id: 'evt_002',
        started_at: '2024-02-14T18:00:00',
        ended_at: '2024-02-14T22:00:00',
        primary_location: '서울 용산구 이태원동',
        photo_count: 8,
        summary: '이태원 재즈바에서 칵테일 한잔',
        cover_photo_id: 'photo_005'
    }
];

// 50개의 목킹 사진을 다양한 종횡비와 이벤트로 생성합니다.
const generateMockPhotos = () => {
    const photos = [];
    let currentDate = new Date('2023-01-01T10:00:00'); // 옛날부터 시작

    // 5~10개의 이벤트를 임의로 생성하기 위해 이벤트 목록을 미리 정의합니다.
    const eventCount = 8;
    const LOCATIONS = ['서울 홍대', '부산 해운대', '제주도 애월', '강원도 강릉', '서울 이태원', '오사카 유니버설', '도쿄 시부야', '경주 황리단길'];

    // 사진을 8개의 이벤트에 균등하게 분배합니다.
    const photosPerEvent = Math.ceil(50 / eventCount);

    for (let i = 1; i <= 50; i++) {
        // 인덱스를 기반으로 이벤트 ID 결정 (예: 1~7번 사진은 evt_0, 8~14번 사진은 evt_1...)
        const eventIndex = Math.min(Math.floor((i - 1) / photosPerEvent), eventCount - 1);
        const eventId = `evt_${eventIndex.toString().padStart(3, '0')}`;
        const locationName = LOCATIONS[eventIndex];

        // 이벤트가 바뀔 때마다 날짜를 크게 건너뛰고, 첫 사진은 초기 날짜를 사용
        if (i > 1 && (i - 1) % photosPerEvent === 0) {
            currentDate = new Date(currentDate.getTime() + (Math.random() * 86400000 * 30)); // 최대 30일 후
        } else if (i > 1) {
            // 같은 이벤트 내에서는 시간만 조금씩 흐릅니다 (몇분~몇시간)
            currentDate = new Date(currentDate.getTime() + (Math.random() * 3600000 * 2)); // 최대 2시간 후
        }

        // 인덱스에 따라 종횡비를 임의로 다양하게 설정
        let width = 800;
        let height = 800;

        if (i % 3 === 0) {
            height = 1200; // 세로 사진
        } else if (i % 5 === 0) {
            width = 1200;  // 가로 사진
        }

        photos.push({
            id: `photo_${i.toString().padStart(3, '0')}`,
            event_id: eventId,
            url: `https://picsum.photos/id/${100 + i}/${width}/${height}`,
            city: locationName.split(' ')[0], // ex: '서울'
            building: i % 2 === 0 ? '카페' : null,
            road: locationName, // ex: '서울 홍대'
            taken_at: currentDate.toISOString(),
            tags: ['추억', `태그${i}`],
            caption: `테스트 사진 ${i} (${width}x${height})`
        });
    }
    return photos;
};

export const MOCK_PHOTOS = generateMockPhotos();
