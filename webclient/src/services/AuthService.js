// src/services/AuthService.js
import axios from 'axios';

export const login = async (email, password) => {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);

    try {
        const response = await axios.post(`${process.env.REACT_APP_API_URL}/login`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });

        console.log(response.data)

        if (response.data.access_token) {
            localStorage.setItem('user', JSON.stringify(response.data));
        }
        
        return response.data;
    } catch (error) {
        console.error('Login error:', error.response);
        throw error;
    }
};

export const register = async (email, password) => {
    try {
        const response = await axios.post(`${process.env.REACT_APP_API_URL}/users`, {
            email, password
        }, {
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (response.data.access_token) {
            localStorage.setItem('user', JSON.stringify(response.data));
        }
        
        return response.data;
    } catch (error) {
        console.error('Login error:', error.response);
        throw error;
    }
};

export const logout = () => {
    localStorage.removeItem('user');
};

export const getCurrentUser = () => {
    return JSON.parse(localStorage.getItem('user'));
};
