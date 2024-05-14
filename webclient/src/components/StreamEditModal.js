import React, { useState, useEffect } from 'react';
import { Modal, Button, Form } from 'react-bootstrap';

// Define the fields to be displayed
const fields = ['label', 'stream_key', 'youtube_key', 'noise_reduction'];

const initialFormState = {
    label: '',
    stream_key: '',
    youtube_key: '',
    noise_reduction: ''
};

const StreamEditModal = ({ showModal, setShowModal, handleSave, initialData = {}, loading = false, handleDeleteClick }) => {
    const [formState, setFormState] = useState({ ...initialFormState });

    useEffect(() => {
        // Filter initialData to include only the specified fields
        const filteredData = fields.reduce((acc, key) => {
            if (key in initialData) {
                acc[key] = initialData[key];
            }
            return acc;
        }, {});
        setFormState({ ...initialFormState, ...filteredData });
    }, [initialData]);

    const setVariable = (key, value) => {
        setFormState(prevState => ({
            ...prevState,
            [key]: value
        }));
    };

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setVariable(name, value);
    };

    const handleSubmit = () => {
        handleSave(initialData.uuid, formState);
    };

    return (
        <Modal show={showModal} onHide={() => setShowModal(false)}>
            <Modal.Header closeButton>
                <Modal.Title>{'Edit Stream Server'}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    {fields.map(key => (
                        <Form.Group key={key}>
                            <Form.Label>{key === 'label' ? 'Name' : key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</Form.Label>
                            <Form.Control
                                type="text"
                                name={key}
                                value={formState[key] || ""}
                                onChange={handleInputChange}
                            />
                        </Form.Group>
                    ))}
                </Form>
            </Modal.Body>
            <Modal.Footer className="d-flex justify-content-between">
                <div>
                    <Button variant="danger" onClick={async () => {
                        await handleDeleteClick(initialData);
                    }} disabled={loading}>
                        Delete
                    </Button>
                </div>
                <div>
                    <Button variant="secondary" style={{ marginRight: "5px" }} onClick={() => setShowModal(false)}>Cancel</Button>
                    <Button variant="primary" onClick={handleSubmit} disabled={loading}>
                        {loading ? 'Saving...' : 'Save'}
                    </Button>
                </div>
            </Modal.Footer>
        </Modal>
    );
};

export default StreamEditModal;
