import React, { useState, useEffect } from 'react';
import './Projects.css';

export default function Projects({ role }) {
  const [projects, setProjects] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    client: '',
    status: 'active',
    budget: '',
    deadline: ''
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [selectedProject, setSelectedProject] = useState(null);

  const token = localStorage.getItem('token');
  const headers = { 'Authorization': `Bearer ${token}` };

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const res = await fetch('http://localhost:8000/projects/', { headers });
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
      }
    } catch (err) {
      console.error('Error fetching projects:', err);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    
    try {
      const res = await fetch('http://localhost:8000/projects/', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(formData)
      });

      if (res.ok) {
        const newProject = await res.json();
        setProjects([...projects, newProject]);
        setMessage('✅ Project created successfully!');
        setFormData({
          name: '',
          description: '',
          client: '',
          status: 'active',
          budget: '',
          deadline: ''
        });
        setShowForm(false);
        setTimeout(() => setMessage(''), 3000);
      } else {
        const error = await res.json();
        setMessage('❌ ' + (error.detail || 'Failed to create project'));
      }
    } catch (err) {
      setMessage('❌ Error: ' + err.message);
    }
    setLoading(false);
  };

  const handleDeleteProject = async (id) => {
    if (!window.confirm('Are you sure you want to delete this project?')) return;

    try {
      const res = await fetch(`http://localhost:8000/projects/${id}`, {
        method: 'DELETE',
        headers
      });

      if (res.ok) {
        setProjects(projects.filter(p => p.id !== id));
        setMessage('✅ Project deleted');
        setTimeout(() => setMessage(''), 3000);
      } else {
        setMessage('❌ Failed to delete project');
      }
    } catch (err) {
      setMessage('❌ Error: ' + err.message);
    }
  };

  return (
    <div className="projects-container">
      <div className="projects-header">
        <h1>📊 Projects Management</h1>
        {role === 'admin' && (
          <button 
            className="btn btn-primary"
            onClick={() => setShowForm(!showForm)}
          >
            {showForm ? 'Cancel' : '+ New Project'}
          </button>
        )}
      </div>

      {message && (
        <div className={`project-message ${message.includes('✅') ? 'success' : 'error'}`}>
          {message}
        </div>
      )}

      {showForm && role === 'admin' && (
        <div className="project-form-card">
          <h2>Create New Project</h2>
          <form onSubmit={handleCreateProject}>
            <div className="form-group">
              <label>Project Name *</label>
              <input
                type="text"
                name="name"
                placeholder="e.g., Customer Portal Redesign"
                value={formData.name}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="form-group">
              <label>Description</label>
              <textarea
                name="description"
                placeholder="Project description..."
                value={formData.description}
                onChange={handleInputChange}
                rows="3"
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Client Name</label>
                <input
                  type="text"
                  name="client"
                  placeholder="Client name"
                  value={formData.client}
                  onChange={handleInputChange}
                />
              </div>

              <div className="form-group">
                <label>Status</label>
                <select name="status" value={formData.status} onChange={handleInputChange}>
                  <option value="active">Active</option>
                  <option value="planning">Planning</option>
                  <option value="on-hold">On Hold</option>
                  <option value="completed">Completed</option>
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Budget</label>
                <input
                  type="number"
                  name="budget"
                  placeholder="Budget amount"
                  value={formData.budget}
                  onChange={handleInputChange}
                />
              </div>

              <div className="form-group">
                <label>Deadline</label>
                <input
                  type="date"
                  name="deadline"
                  value={formData.deadline}
                  onChange={handleInputChange}
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Creating...' : 'Create Project'}
            </button>
          </form>
        </div>
      )}

      <div className="projects-grid">
        {projects.length === 0 ? (
          <div className="no-projects">
            <p>📭 No projects yet</p>
            {role === 'admin' && <p>Click "New Project" to create one</p>}
          </div>
        ) : (
          projects.map(project => (
            <div 
              key={project.id} 
              className="project-card"
              onClick={() => setSelectedProject(selectedProject?.id === project.id ? null : project)}
            >
              <div className="project-header-card">
                <h3>{project.name}</h3>
                <span className={`status-badge status-${project.status || 'active'}`}>
                  {project.status || 'Active'}
                </span>
              </div>

              {project.description && (
                <p className="project-description">{project.description}</p>
              )}

              <div className="project-details">
                {project.client && (
                  <div className="detail-item">
                    <strong>Client:</strong> {project.client}
                  </div>
                )}
                {project.budget && (
                  <div className="detail-item">
                    <strong>Budget:</strong> ${project.budget}
                  </div>
                )}
                {project.deadline && (
                  <div className="detail-item">
                    <strong>Deadline:</strong> {new Date(project.deadline).toLocaleDateString()}
                  </div>
                )}
              </div>

              {selectedProject?.id === project.id && role === 'admin' && (
                <button 
                  className="btn btn-danger"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteProject(project.id);
                  }}
                >
                  🗑️ Delete Project
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
