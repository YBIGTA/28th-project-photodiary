import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

const client = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const api = {
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

    // Events
    getLastEvent: async () => {
        const response = await client.get('/events/last');
        return response.data;
    },
};
