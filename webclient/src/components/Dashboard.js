// src/components/Dashboard.js
import React, { useState, useEffect } from 'react';
import { useUser } from '../contexts/UserContext';
import { useNavigate } from 'react-router-dom';
import Workspaces from './Workspaces';

function Dashboard() {
    const navigate = useNavigate();
    const { user, setUser } = useUser();

    useEffect(() => {
        console.log("USER", user);
        if (!user) {
            navigate('/login');
        }
    }, [user, navigate]);

    return (
        <div>
            <Workspaces />
        </div>
    );
}

export default Dashboard;
