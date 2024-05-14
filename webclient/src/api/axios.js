
import axios from 'axios';

const API = axios.create({
    baseURL: process.env.REACT_APP_API_URL,
});

// Function to inject the token into headers of each request
export const setAuthToken = (token) => {
    if (token) {
        API.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
        delete API.defaults.headers.common['Authorization'];
    }
};

export default API;

