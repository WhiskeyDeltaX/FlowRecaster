import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { Container, Row, Col, ListGroup, Button, Modal, Form, Spinner } from 'react-bootstrap';
import API from '../api/axios';
import { useUser } from '../contexts/UserContext';

function WorkspaceView() {
    const { uuid } = useParams();
    const [workspace, setWorkspace] = useState(null);
    const [streamServers, setStreamServers] = useState([]);
    const [selectedServer, setSelectedServer] = useState(null);
    const [showModal, setShowModal] = useState(false);
    const [newServerName, setNewServerName] = useState('');
    const [loading, setLoading] = useState(false);
    const ws = useRef(null);
    const { user, setUser } = useUser();
    const [shouldReconnect, setShouldReconnect] = useState(true);
    const [retryCount, setRetryCount] = useState(0);
    const maxRetries = 5;

    useEffect(() => {
        fetchWorkspace();
        fetchStreamServers();

        connectWebSocket();

        return () => {
            setShouldReconnect(false); // Prevent reconnection on component unmount
            if (ws.current) {
                ws.current.close();
            }
        };
    }, [uuid]);

    const connectWebSocket = () => {
        const token = user.access_token;
        ws.current = new WebSocket(`ws://${process.env.REACT_APP_API_IP}/ws/updates/${uuid}?token=${token}`);

        ws.current.onopen = () => {
            console.log('WebSocket Connected');
            setRetryCount(0); // Reset retry count on successful connection
        };

        ws.current.onmessage = (e) => {
            const message = JSON.parse(e.data);
            console.log('Received message:', message);
        };

        ws.current.onclose = () => {
            console.log('WebSocket Disconnected');
            if (shouldReconnect && retryCount < maxRetries) {
                setTimeout(() => {
                    console.log('Attempting to reconnect...');
                    connectWebSocket();
                    setRetryCount(retryCount + 1);
                }, 2000 * retryCount); // Exponential backoff
            }
        };

        ws.current.onerror = (error) => {
            console.error('WebSocket Error:', error);
            ws.current.close();
        };
    };

    const handleWebSocketMessage = (message) => {
        if (message.type === 'server_online' && message.data.uuid) {
            // Update the state of the specific server to reflect it's now online
            const updatedServers = streamServers.map(server => {
                if (server.uuid === message.data.uuid) {
                    return { ...server, online: true, last_heartbeat: new Date().toISOString() };
                }
                return server;
            });
            setStreamServers(updatedServers);
            console.log('Server Online:', message.data);
        }
    };

    const fetchWorkspace = async () => {
        try {
            const response = await API.get(`/workspaces/${uuid}`);
            setWorkspace(response.data);
        } catch (error) {
            console.error('Failed to fetch workspace details:', error);
        }
    };

    const fetchStreamServers = async () => {
        try {
            const response = await API.get(`/streamservers/${uuid}`);
            setStreamServers(response.data);
            setSelectedServer(response.data[0] || null);  // Select the first server by default
        } catch (error) {
            console.error('Failed to fetch stream servers:', error);
        }
    };

    const handleCreateServer = async () => {
        setLoading(true);
        try {
            const response = await API.post(`/streamservers/`, { label: newServerName, workspace: uuid });
            setStreamServers([...streamServers, response.data]);
            console.log("Response", response)
            setShowModal(false);
            setNewServerName('');
        } catch (error) {
            console.error('Error creating new stream server:', error);
        } finally {
            setLoading(false);
        }
    };

    if (!workspace || !streamServers) {
        return (
            <Container className="d-flex justify-content-center align-items-center" style={{ height: "80vh" }}>
                <Spinner animation="border" />
            </Container>
        );
    }

    return (
        <Container>
            <Row className="justify-content-between align-items-center my-3">
                <Col>
                    <h2>{workspace.name}</h2>
                </Col>
                <Col className="text-end">
                    <Button onClick={() => setShowModal(true)}>Create Stream Server</Button>
                </Col>
            </Row>

            <Row>
                <Col md={4}>
                    <ListGroup>
                        {streamServers.map(server => (
                            <ListGroup.Item key={server.uuid} action onClick={() => setSelectedServer(server)}>
                                {server.label}
                            </ListGroup.Item>
                        ))}
                    </ListGroup>
                </Col>
                <Col md={8}>
                    {selectedServer && (
                        <>
                            <h3>{selectedServer.label}</h3>
                            <video controls width="100%">
                                <source src={`http://${selectedServer.ip}:19751/hls/stream.m3u8`} type="application/x-mpegURL" />
                            </video>
                            <div>
                                {/* Display server details */}
                                <p>Region: {selectedServer.region}</p>
                                <p>IP: {selectedServer.ip}</p>
                                {/* Include other details as necessary */}
                            </div>
                        </>
                    )}
                </Col>
            </Row>

            {/* Create Stream Server Modal */}
            <Modal show={showModal} onHide={() => setShowModal(false)}>
                <Modal.Header closeButton>
                    <Modal.Title>Create Stream Server</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Form>
                        <Form.Group>
                            <Form.Label>Name</Form.Label>
                            <Form.Control
                                type="text"
                                value={newServerName}
                                onChange={(e) => setNewServerName(e.target.value)}
                            />
                        </Form.Group>
                    </Form>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowModal(false)}>Close</Button>
                    <Button variant="primary" onClick={handleCreateServer} disabled={loading}>
                        {loading ? 'Creating...' : 'Create'}
                    </Button>
                </Modal.Footer>
            </Modal>
        </Container>
    );
}

export default WorkspaceView;
