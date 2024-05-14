import React, { useState, useEffect } from 'react';
import { Modal, Button, Form, ListGroup, Container, Spinner, Row, Col } from 'react-bootstrap';
import { PencilSquare, Trash, PlusCircle, Eye } from 'react-bootstrap-icons'; // Ensure you have these icons
import API from '../api/axios';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../contexts/UserContext';

function Workspaces() {
    const [workspaces, setWorkspaces] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [showAddModal, setShowAddModal] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [currentWorkspace, setCurrentWorkspace] = useState({});
    const [newWorkspaceName, setNewWorkspaceName] = useState('');
    const navigate = useNavigate();
    const { user, setUser } = useUser();

    useEffect(() => {
        console.log(user);
        fetchWorkspaces();
    }, []);

    const fetchWorkspaces = async () => {
        try {
            const response = await API.get(`/workspaces`);
            console.log("Response", response.data);
            setWorkspaces(response.data);
        } catch (error) {
            console.error('Error fetching workspaces:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleDeleteWorkspace = async (id) => {
        try {
            await API.delete(`/workspaces/${id}`);
            setWorkspaces(workspaces.filter(ws => ws.uuid !== id));
            setShowDeleteConfirm(false);
        } catch (error) {
            console.error('Error deleting workspace:', error);
        }
    };

    const handleAddWorkspace = async () => {
        try {
            const response = await API.post(`/workspaces`, { name: newWorkspaceName });
            setWorkspaces([...workspaces, response.data]);
            setShowAddModal(false);
            setNewWorkspaceName('');
        } catch (error) {
            console.error('Error adding workspace:', error);
        }
    };

    const handleEditWorkspace = async (id) => {
        try {
            const response = await API.put(`/workspaces/${id}`, { name: currentWorkspace.name });
            const updatedWorkspaces = workspaces.map(ws => ws.uuid === id ? response.data : ws);
            setWorkspaces(updatedWorkspaces);
            setShowEditModal(false);
        } catch (error) {
            console.error('Error updating workspace:', error);
        }
    };

    if (isLoading) {
        return (
            <Container className="d-flex justify-content-center align-items-center" style={{ height: "80vh" }}>
                <Spinner animation="border" />
            </Container>
        );
    }

    return (
        <Container className="mt-4">
            <Row className="justify-content-between align-items-center my-3">
                <Col>
                    <h2>Workspaces</h2>
                </Col>
                <Col className="text-end">
                    <Button 
                        variant="primary" 
                        onClick={() => setShowAddModal(true)}
                        disabled={user.user.role !== 'admin'}  // Button is disabled if user's role is not 'admin'
                    >
                        <PlusCircle className="mb-1 mr-2" /> Add Workspace
                    </Button>
                </Col>
            </Row>

            <ListGroup className="my-3">
                {workspaces.map(workspace => (
                    <ListGroup.Item key={workspace.uuid} className="d-flex justify-content-between align-items-center p-3">
                        {workspace.name}
                        <div>
                            <Button variant="outline-primary" size="sm" onClick={() => navigate(`/workspace/${workspace.uuid}`)}>
                                <Eye /> View
                            </Button>
                            {' '}
                            <Button variant="outline-secondary" size="sm" disabled={user.user.role !== "admin"} onClick={() => {
                                setCurrentWorkspace(workspace);
                                setShowEditModal(true);
                            }}>
                                <PencilSquare /> Edit
                            </Button>
                            {' '}
                            <Button variant="outline-danger" size="sm" disabled={user.user.role !== "admin"} onClick={() => {
                                setCurrentWorkspace(workspace);
                                setShowDeleteConfirm(true);
                            }}>
                                <Trash /> Delete
                            </Button>
                        </div>
                    </ListGroup.Item>
                ))}
            </ListGroup>

            {/* Modals for Add, Edit, Delete */}
            {renderModals()}
        </Container>
    );

    function renderModals() {
        return (
            <>
                {/* Add Workspace Modal */}
                <Modal show={showAddModal} onHide={() => setShowAddModal(false)}>
                    <Modal.Header closeButton>
                        <Modal.Title>Add a New Workspace</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <Form>
                            <Form.Group>
                                <Form.Label>Workspace Name</Form.Label>
                                <Form.Control
                                    type="text"
                                    value={newWorkspaceName}
                                    onChange={(e) => setNewWorkspaceName(e.target.value)}
                                />
                            </Form.Group>
                        </Form>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={() => setShowAddModal(false)}>Close</Button>
                        <Button variant="primary" onClick={handleAddWorkspace}>Create Workspace</Button>
                    </Modal.Footer>
                </Modal>

                {/* Edit Workspace Modal */}
                <Modal show={showEditModal} onHide={() => setShowEditModal(false)}>
                    <Modal.Header closeButton>
                        <Modal.Title>Edit Workspace</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <Form>
                            <Form.Group>
                                <Form.Label>Workspace Name</Form.Label>
                                <Form.Control
                                    type="text"
                                    value={currentWorkspace.name}
                                    onChange={(e) => setCurrentWorkspace({...currentWorkspace, name: e.target.value})}
                                />
                            </Form.Group>
                        </Form>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={() => setShowEditModal(false)}>Close</Button>
                        <Button variant="primary" onClick={() => handleEditWorkspace(currentWorkspace.uuid)}>Save Changes</Button>
                    </Modal.Footer>
                </Modal>

                {/* Confirm Delete Modal */}
                <Modal show={showDeleteConfirm} onHide={() => setShowDeleteConfirm(false)}>
                    <Modal.Header closeButton>
                        <Modal.Title>Confirm Delete</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>Are you sure you want to delete this workspace?</Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={() => setShowDeleteConfirm(false)}>Cancel</Button>
                        <Button variant="danger" onClick={() => handleDeleteWorkspace(currentWorkspace.uuid)}>Delete</Button>
                    </Modal.Footer>
                </Modal>
            </>
        );
    }
}

export default Workspaces;
