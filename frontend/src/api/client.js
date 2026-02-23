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

// Interceptor to attach JWT token
client.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

const realApi = {
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

// Add mock login/register and upload support to mockApi temporarily if USE_MOCK is true
if (USE_MOCK) {
    if (!mockApi.login) {
        mockApi.login = async (email, password) => {
            console.log("Mock Login:", email);
            return { access_token: "mock-token-123", user_id: 1, username: email.split('@')[0] };
        };
    }
    if (!mockApi.register) {
        mockApi.register = async (username, email, password) => {
            console.log("Mock Register:", username);
            return { access_token: "mock-token-123", user_id: 1, username };
        };
    }
    if (!mockApi.uploadPhoto) {
        mockApi.uploadPhoto = async (file) => {
            console.log("Mock Upload:", file.name);
            return new Promise((resolve) => {
                setTimeout(() => {
                    resolve({ photo_id: Math.floor(Math.random() * 1000), s3_url: "mock-url" });
                }, 1500); // 1.5초 지연
            });
        };
    }
}

// Export either real or mock API
export const api = USE_MOCK ? mockApi : realApi;

if (USE_MOCK) {
    console.warn("⚠️ [API] Application is running in MOCK mode. Real backend is ignored.");
}
