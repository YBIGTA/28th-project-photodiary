import axios from 'axios';
import { mockApi } from './mockClient';

// ==========================================
// TOGGLE MOCK MODE HERE
// ==========================================
const USE_MOCK = true;

const API_BASE_URL = 'http://localhost:8000/api';

const client = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

const realApi = {
    // Photos
    getPhotos: async (limit = 100) => {
        const response = await client.get('/photos/', { params: { limit } });
        return response.data;
    },

    searchPhotos: async (query, limit = 20) => {
        const response = await client.post('/photos/search', null, {
            params: { query, limit },
        });
        return response.data;
    },

    getPhotoImageUrl: (photoId) => {
        return `${API_BASE_URL}/photos/${photoId}/image`;
    },

    // Chat
    chat: async (query, userId = 1) => {
        const response = await client.post('/chat/', { query, user_id: userId });
        return response.data;
    },

    // Events
    getLastEvent: async () => {
        const response = await client.get('/events/last');
        return response.data;
    },
};

// Export either real or mock API
export const api = USE_MOCK ? mockApi : realApi;

if (USE_MOCK) {
    console.warn("⚠️ [API] Application is running in MOCK mode. Real backend is ignored.");
}
