// src/components/Register.js
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { register } from '../services/AuthService';
import { Container, Row, Col, Card, Form, Button, Alert } from 'react-bootstrap';
import { useUser } from '../contexts/UserContext';

function Register() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [errorMessage, setErrorMessage] = useState('');
    const navigate = useNavigate();
    const { user } = useUser();

    useEffect(() => {
        if (user) {
            navigate('/dashboard');
        }
    }, [user, navigate]);

    const handleRegistration = async (e) => {
        e.preventDefault();
        // API call integration logic here
        try {
            // Assuming `register` function sends data to your backend and handles registration
            const response = await register(email, password);
            if (response.success) {
                navigate('/login');  // Redirect to login after successful registration
            } else {
                setErrorMessage('Registration failed. Please try again.');
            }
        } catch (error) {
            console.error('Registration error:', error);
            setErrorMessage('Registration failed. Please try again.');
        }
    };

    return (
        <Container className="mt-5">
            <Row className="justify-content-center">
                <Col md={6}>
                    <Card>
                        <Card.Header>Register</Card.Header>
                        <Card.Body>
                            <Form onSubmit={handleRegistration}>
                                <Form.Group className="mb-3" controlId="email">
                                    <Form.Label>Email</Form.Label>
                                    <Form.Control
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                    />
                                </Form.Group>
                                <Form.Group className="mb-3" controlId="password">
                                    <Form.Label>Password</Form.Label>
                                    <Form.Control
                                        type="password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        required
                                    />
                                </Form.Group>
                                <Button variant="primary" type="submit">Register</Button>
                                {errorMessage && <Alert variant="danger" className="mt-2">{errorMessage}</Alert>}
                            </Form>
                        </Card.Body>
                    </Card>
                </Col>
            </Row>
        </Container>
    );
}

export default Register;
