import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { Container, Row, Col, ListGroup, Button, Modal, Form,
    Spinner, Badge, Table } from 'react-bootstrap';
import API from '../api/axios';
import { useUser } from '../contexts/UserContext';
import VideoJS from './VideoJS'
import videojs from 'video.js';

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
    const playerRef = React.useRef(null);

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
        ws.current = new WebSocket(`${process.env.REACT_APP_API_SOCKET}/ws/updates/${uuid}?token=${token}`);

        ws.current.onopen = () => {
            console.log('WebSocket Connected');
            setRetryCount(0); // Reset retry count on successful connection
        };

        ws.current.onmessage = (e) => {
            const message = JSON.parse(e.data);
            console.log('Received message:', message);
            handleWebSocketMessage(message);
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
            setStreamServers(currentStreamServers => {
                const updateServer = currentStreamServers.find(s => s.uuid === message.data.uuid);

                if (updateServer) {
                    Object.assign(updateServer, message.data);

                    if (selectedServer && selectedServer.uuid === updateServer.uuid) {
                        setSelectedServer(updateServer);
                    }
                } else {
                    currentStreamServers.push(message.data);
                }
                
                return currentStreamServers.slice();
            });
        } else if (message.type === 'status_report' && message.data.uuid) {
            setStreamServers(currentStreamServers => {
                console.log("Current Stream Servers", currentStreamServers)

                const updateServer = currentStreamServers.find(s => s.uuid === message.data.uuid);

                if (updateServer) {
                    updateServer.hasHeartbeat = true;
                    updateServer.stream1 = message.data.status.stream1_live;
                    updateServer.last_status_update = message.data.status;

                    if (selectedServer && selectedServer.uuid === updateServer.uuid) {
                        setSelectedServer(updateServer);
                    }
                }

                return currentStreamServers.slice();
            });
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
            console.log(response);
            setStreamServers(response.data);
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

    function decideBestSource(hlsUrl, dashUrl) {
        // Simple example: Prefer DASH if supported, else fallback to HLS
        let type = 'application/dash+xml';
        let src = dashUrl;
        if (!MediaSource || !MediaSource.isTypeSupported(type)) {
            type = 'application/x-mpegURL'; // Fallback to HLS
            src = hlsUrl;
        }
        return { src, type };
    }

    let videoSrc, videoType;

    if (selectedServer) {
        console.log("Trying to find best src type", selectedServer);

        const { src, type } = decideBestSource(
            `http://${selectedServer.ip}:19751/hls/${selectedServer.uuid}.m3u8`,
            `http://${selectedServer.ip}:19751/dash/${selectedServer.uuid}.mpd`
        );

        console.log("Found best", src, type);

        videoSrc = src;
        videoType = type;
    }

    const videoJsOptions = {
        autoplay: true,
        controls: true,
        responsive: true,
        fluid: true,
        sources: [{
          src: videoSrc,
          type: videoType
        }]
    };
    
    const handlePlayerReady = (player) => {
        playerRef.current = player;
    
        // You can handle player events here, for example:
        player.on('waiting', () => {
          videojs.log('player is waiting');
        });
    
        player.on('dispose', () => {
          videojs.log('player will dispose');
        });
    };
    
    console.log("We good?", selectedServer && selectedServer.ip && videoSrc && videoType)

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
                            <ListGroup.Item key={server.uuid} action onClick={() => setSelectedServer(server)}  className="d-flex justify-content-between align-items-center mb-2">
                                {server.label}
                                <div className="d-flex" style={{gap: "5px"}}>
                                    <Badge pill bg={server.hasHeartbeat ? "success" : "danger"}>
                                        {server.hasHeartbeat ? "Server" : "Server"}
                                    </Badge>
                                    <Badge pill bg={server.stream1 ? "success" : "danger"}>
                                        {server.stream1 ? "Stream 1" : "Stream 1"}
                                    </Badge>
                                </div>
                            </ListGroup.Item>
                        ))}
                    </ListGroup>
                </Col>
                <Col md={8}>
                    {selectedServer && (
                        <>
                            <div>
                                <h3>{selectedServer.label}</h3>
                            </div>
                            {selectedServer.ip && <VideoJS key={videoSrc} options={videoJsOptions} onReady={handlePlayerReady} />}
                            <div>
                                <h4 className="mt-3">Computed Information</h4>
                                <Table striped bordered hover size="sm" className="mt-3">
                                    <tbody>
                                        <tr>
                                            <td>Stream URL</td>
                                            <td>rtmp://{selectedServer.ip}:8453/live/{selectedServer.uuid}</td>
                                        </tr>
                                        <tr>
                                            <td>Stream HLS</td>
                                            <td>http://{selectedServer.ip}:19751/hls/{selectedServer.uuid}.m3u8</td>
                                        </tr>
                                        <tr>
                                            <td>Stream DASH</td>
                                            <td>http://{selectedServer.ip}:19751/dash/{selectedServer.uuid}.mpd</td>
                                        </tr>
                                    </tbody>
                                </Table>
                                
                                {selectedServer.last_status_update && (<>
                                    <h4 className="mt-3">Last Server Status</h4>
                                    <Table striped bordered hover size="sm" className="mt-3">
                                        <tbody>
                                            <tr>
                                                <td>Date Created</td>
                                                <td>{new Date(selectedServer.last_status_update.date_created).toLocaleString()}</td>
                                            </tr>
                                            <tr>
                                                <td>CPU Usage</td>
                                                <td>{selectedServer.last_status_update.cpu_usage}%</td>
                                            </tr>
                                            <tr>
                                                <td>RAM Usage</td>
                                                <td>{selectedServer.last_status_update.ram_usage}%</td>
                                            </tr>
                                            <tr>
                                                <td>Bytes Sent</td>
                                                <td>
                                                    {selectedServer.last_status_update.bytes_sent ? (selectedServer.last_status_update.bytes_sent * 8 / 1000).toLocaleString() + ' kbps' : 'N/A'}
                                                </td>
                                            </tr>
                                            <tr>
                                                <td>Bytes Received</td>
                                                <td>
                                                    {selectedServer.last_status_update.bytes_recv ? (selectedServer.last_status_update.bytes_recv * 8 / 1000).toLocaleString() + ' kbps' : 'N/A'}
                                                </td>
                                            </tr>
                                            <tr>
                                                <td>Selected Source</td>
                                                <td>{selectedServer.last_status_update.selected_source}</td>
                                            </tr>
                                            <tr>
                                                <td>YouTube Key</td>
                                                <td>{selectedServer.last_status_update.youtube_key}</td>
                                            </tr>
                                            <tr>
                                                <td>FFmpeg Active</td>
                                                <td>{selectedServer.last_status_update.ffmpeg_active ? "Yes" : "No"}</td>
                                            </tr>
                                            <tr>
                                                <td>Stream 1 Live</td>
                                                <td>{selectedServer.last_status_update.stream1_live ? "Yes" : "No"}</td>
                                            </tr>
                                            <tr>
                                                <td>Stream 2 Live</td>
                                                <td>{selectedServer.last_status_update.stream2_live ? "Yes" : "No"}</td>
                                            </tr>
                                            <tr>
                                                <td>Noise Reduction</td>
                                                <td>{selectedServer.last_status_update.noise_reduction || "N/A"}</td>
                                            </tr>
                                            <tr>
                                                <td>Stream 1 URL</td>
                                                <td>{selectedServer.last_status_update.stream1_url}</td>
                                            </tr>
                                            <tr>
                                                <td>Stream 2 URL</td>
                                                <td>{selectedServer.last_status_update.stream2_url}</td>
                                            </tr>
                                        </tbody>
                                    </Table>
                                </>)}
                                <h4 className="mt-3">Server Information</h4>
                                <Table striped bordered hover size="sm">
                                    <tbody>
                                        <tr>
                                            <td>Region</td>
                                            <td>{selectedServer.region || "N/A"}</td>
                                        </tr>
                                        <tr>
                                            <td>IP</td>
                                            <td>{selectedServer.ip || "N/A"}</td>
                                        </tr>
                                        <tr>
                                            <td>Operating System</td>
                                            <td>{selectedServer.os || "N/A"}</td>
                                        </tr>
                                        <tr>
                                            <td>Plan</td>
                                            <td>{selectedServer.plan || "N/A"}</td>
                                        </tr>
                                        <tr>
                                            <td>Cores</td>
                                            <td>{selectedServer.cores || "N/A"}</td>
                                        </tr>
                                        <tr>
                                            <td>Memory</td>
                                            <td>{selectedServer.memory ? `${selectedServer.memory} GB` : "N/A"}</td>
                                        </tr>
                                        <tr>
                                            <td>Cost</td>
                                            <td>{selectedServer.cost ? `$${selectedServer.cost}` : "N/A"}</td>
                                        </tr>
                                        <tr>
                                            <td>Hostname</td>
                                            <td>{selectedServer.hostname || "N/A"}</td>
                                        </tr>
                                        <tr>
                                            <td>Last Heartbeat</td>
                                            <td>{selectedServer.lastHeartbeat ? new Date(selectedServer.lastHeartbeat).toLocaleString() : "N/A"}</td>
                                        </tr>
                                        <tr>
                                            <td>Last Boot</td>
                                            <td>{selectedServer.lastBoot ? new Date(selectedServer.lastBoot).toLocaleString() : "N/A"}</td>
                                        </tr>
                                    </tbody>
                                </Table>
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
