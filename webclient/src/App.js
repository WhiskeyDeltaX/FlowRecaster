// src/App.js
import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import HomePage from './components/HomePage';
import Register from './components/Register';
import Workspaces from './components/Workspaces';
import WorkspaceView from './components/WorkspaceView';

function App() {
    return (
        <Router>
            <Navbar />
            <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/workspaces" element={<Workspaces />} />
                <Route path="/" element={<HomePage />} />
                <Route path="/workspace/:uuid" element={<WorkspaceView />} />
            </Routes>
        </Router>
    );
}

export default App;
