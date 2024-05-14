// src/components/HomePage.js
import React from 'react';
import { Container, Row, Col, Button, Card, Image } from 'react-bootstrap';

function HomePage() {
    return (
        <Container fluid style={{ paddingLeft: 0, paddingRight: 0 }}>
            {/* Hero Section */}
            <Row className="bg-dark text-white text-center p-4 g-0">
                <h1>Welcome to FlowRecaster</h1>
                <p>An overengineered RTMP restreamer.</p>
            </Row>

            {/* Introduction Section */}
            <Row className="justify-content-center p-4 g-0">
                <Col md={8}>
                    <h2 className="text-center">Dynamic RTMP Stream Management</h2>
                    <p className="mt-4">
                        FlowRecaster is a sophisticated FastAPI application designed for dynamic
                        management of RTMP streams. It enables automatic creation of instances that
                        can take in an RTMP stream and restream it to YouTube using FFmpeg. This system
                        is designed to be highly scalable and efficient, providing robust stream management
                        capabilities.
                    </p>
                </Col>
            </Row>

            {/* Components Section */}
            <Row className="m-4">
                <Col md={4}>
                    <Card className="m-2">
                        <Card.Body>
                            <Card.Title>Stream Server</Card.Title>
                            <Card.Text>Manages and configures RTMP streams with Nginx.</Card.Text>
                        </Card.Body>
                    </Card>
                </Col>
                <Col md={4}>
                    <Card className="m-2">
                        <Card.Body>
                            <Card.Title>Web Server</Card.Title>
                            <Card.Text>
                                FastAPI backend that provides APIs to control and monitor streams, and dynamically
                                create streaming instances.
                            </Card.Text>
                        </Card.Body>
                    </Card>
                </Col>
                <Col md={4}>
                    <Card className="m-2">
                        <Card.Body>
                            <Card.Title>Web Client</Card.Title>
                            <Card.Text>
                                React-based frontend for interacting with the webserver, offering a Bootstrap-based
                                user interface.
                            </Card.Text>
                        </Card.Body>
                    </Card>
                </Col>
            </Row>

            {/* Call to Action Section */}
            <Row className="justify-content-center mt-4 mb-4 g-0">
                <Col md={6} className="text-center">
                    <Button variant="primary" size="lg">Get Started</Button>
                </Col>
            </Row>

            {/* Footer */}
            <footer className="footer mt-5 p-3 bg-dark text-white text-center fixed-bottom">
                <div>
                    <p>Copyright © 2024 FlowRecaster</p>
                </div>
            </footer>
        </Container>
    );
}

export default HomePage;
