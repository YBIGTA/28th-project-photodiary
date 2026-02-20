import { MOCK_PHOTOS, MOCK_EVENTS } from './mockData';

// Simulate network delay
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

export const mockApi = {
    // Photos
    getPhotos: async (limit = 100) => {
        await delay(500);
        return MOCK_PHOTOS.slice(0, limit);
    },

    searchPhotos: async (query, limit = 20) => {
        console.warn("⚠️ [MOCK API] Searching photos with query:", query);
        await delay(1000); // Simulate AI processing time

        if (!query) return [];

        // Simple filtering for mock
        const lowerQuery = query.toLowerCase();
        const results = MOCK_PHOTOS.filter(p =>
            p.tags.some(t => t.includes(lowerQuery)) ||
            p.caption.includes(lowerQuery) ||
            (p.city && p.city.includes(lowerQuery)) ||
            (p.building && p.building.includes(lowerQuery))
        );

        // If no matches found in mock data, just return random photos to demonstrate UI
        if (results.length === 0) {
            console.log("⚠️ [MOCK API] No exact match, returning random suggestions");
            return [MOCK_PHOTOS[0], MOCK_PHOTOS[1], MOCK_PHOTOS[4]];
        }

        return results.slice(0, limit);
    },

    getPhotoImageUrl: (photoId) => {
        const photo = MOCK_PHOTOS.find(p => p.id === photoId);
        return photo ? photo.url : 'https://via.placeholder.com/400';
    },

    // Events
    getLastEvent: async () => {
        await delay(300);
        return MOCK_EVENTS[0];
    },
};
