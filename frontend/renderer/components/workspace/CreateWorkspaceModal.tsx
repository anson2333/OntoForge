import React, { useState } from 'react';
import { CreateWorkspaceInput } from '../../services/workspace';
import './CreateWorkspaceModal.css';

interface CreateWorkspaceModalProps {
  onClose: () => void;
  onCreateWorkspace: (input: CreateWorkspaceInput) => Promise<unknown>;
}

export const CreateWorkspaceModal: React.FC<CreateWorkspaceModalProps> = ({
  onClose,
  onCreateWorkspace,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [root, setRoot] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    console.log('[CreateWorkspaceModal] handleSubmit called');
    console.log('[CreateWorkspaceModal] name:', name);
    console.log('[CreateWorkspaceModal] description:', description);
    console.log('[CreateWorkspaceModal] root:', root);
    console.log('[CreateWorkspaceModal] onCreateWorkspace:', typeof onCreateWorkspace);
    
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Workspace name is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      console.log('[CreateWorkspaceModal] About to call onCreateWorkspace...');
      await onCreateWorkspace({
        name: trimmedName,
        description: description.trim() || undefined,
        root: root.trim() || undefined,
      });
      console.log('[CreateWorkspaceModal] onCreateWorkspace completed successfully');
      onClose();
    } catch (createError) {
      console.error('[CreateWorkspaceModal] Error during creation:', createError);
      setError(createError instanceof Error ? createError.message : 'Failed to create workspace');
    } finally {
      setIsSubmitting(false);
      console.log('[CreateWorkspaceModal] handleSubmit finished');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="create-workspace-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2>Create Workspace</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="modal-content create-workspace-content">
          <label className="workspace-field">
            <span>Workspace name</span>
            <input
              className="workspace-input"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Example: Optical Transport Benchmark"
              disabled={isSubmitting}
              autoFocus
            />
          </label>

          <label className="workspace-field">
            <span>Description</span>
            <textarea
              className="workspace-input workspace-textarea"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Optional summary of the research workspace"
              disabled={isSubmitting}
              rows={4}
            />
          </label>

          <label className="workspace-field">
            <span>Root path</span>
            <input
              className="workspace-input"
              type="text"
              value={root}
              onChange={(event) => setRoot(event.target.value)}
              placeholder="Optional, e.g. file:///Users/me/research/project"
              disabled={isSubmitting}
            />
          </label>

          <p className="workspace-note">
            Workspaces are currently created for the local owner profile and will map to authenticated ownership once auth is added.
          </p>

          {error && <div className="error-message"><span>{error}</span></div>}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose} disabled={isSubmitting}>Cancel</button>
          <button 
            className="btn-primary" 
            onClick={() => {
              console.log('[CreateWorkspaceModal] Create button clicked!');
              handleSubmit();
            }} 
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Creating...' : 'Create Workspace'}
          </button>
        </div>
      </div>
    </div>
  );
};