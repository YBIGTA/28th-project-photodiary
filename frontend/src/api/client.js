import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

const client = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Interceptor to attach JWT token
client.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export const api = {
    // Auth
    login: async (email, password) => {
        const response = await client.post('/auth/login', { email, password });
        return response.data;
    },

    register: async (username, email, password) => {
        const response = await client.post('/auth/register', { username, email, password });
        return response.data;
    },

    // Photos
    getPhotos: async (limit = 100) => {
        const response = await client.get('/photos/', { params: { limit } });
        return response.data.map(p => ({
            ...p,
            url: api.getPhotoImageUrl(p.id)
        }));
    },

    searchPhotos: async (query, limit = 20) => {
        const response = await client.post('/photos/search', null, {
            params: { query, limit },
        });
        return response.data.map(p => ({
            ...p,
            url: api.getPhotoImageUrl(p.id)
        }));
    },

    getPhotoImageUrl: (photoId) => {
        return `${API_BASE_URL}/photos/${photoId}/image`;
    },

    uploadPhoto: async (file) => {
        const formData = new FormData();
        formData.append('file', file);

        const response = await client.post('/photos/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
        return response.data;
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
