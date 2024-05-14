
// src/components/Navbar.js
import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useUser } from '../contexts/UserContext';

function Navbar() {
    const navigate = useNavigate();
    const { user, setUser } = useUser();

    const handleLogout = () => {
        localStorage.removeItem('user');
        setUser(undefined);
        navigate('/login');
    };

    const isLoggedIn = !!localStorage.getItem('user');

    return (
        <nav className="navbar navbar-expand-lg navbar-light bg-light">
            <div className="container-fluid ml-5 mr-5">
                <Link className="navbar-brand" to="/">FlowRecaster</Link>
                <div className="navbar-nav ms-auto">
                    {isLoggedIn ? (
                        <>
                            <Link className="nav-link" to="/dashboard">Dashboard</Link>
                            <div className="nav-item dropdown">
                                <button className="nav-link dropdown-toggle" id="navbarDropdown" data-bs-toggle="dropdown" aria-expanded="false">
                                    Settings
                                </button>
                                <ul className="dropdown-menu dropdown-menu-end" aria-labelledby="navbarDropdown">  {/* Adjusted here */}
                                    <li><Link className="dropdown-item" to="/user-settings">User Settings</Link></li>
                                    <li><hr className="dropdown-divider" /></li>
                                    <li><button className="dropdown-item" onClick={handleLogout}>Logout</button></li>
                                </ul>
                            </div>
                        </>
                    ) : (
                        <>
                            <Link className="nav-link" to="/login">Login</Link>
                            <Link className="nav-link" to="/register">Register</Link>
                        </>
                    )}
                </div>
            </div>
        </nav>
    );
}

export default Navbar;
