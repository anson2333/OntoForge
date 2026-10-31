import { t, localizeMessage } from '../../i18n';
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
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Workspace name is required");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onCreateWorkspace({
        name: trimmedName,
        description: description.trim() || undefined,
        root: root.trim() || undefined,
      });
      onClose();
    } catch (createError) {
      console.error('[CreateWorkspaceModal] Error during creation:', createError);
      setError(createError instanceof Error ? createError.message : t("Failed to create workspace"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="create-workspace-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2>{t("Create Workspace")}</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="modal-content create-workspace-content">
          <label className="workspace-field">
            <span>{t("Workspace name")}</span>
            <input
              className="workspace-input"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t("Example: Optical Transport Benchmark")}
              disabled={isSubmitting}
              autoFocus
            />
          </label>

          <label className="workspace-field">
            <span>{t("Description")}</span>
            <textarea
              className="workspace-input workspace-textarea"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={t("Optional summary of the research workspace")}
              disabled={isSubmitting}
              rows={4}
            />
          </label>

          <label className="workspace-field">
            <span>{t("Root path")}</span>
            <input
              className="workspace-input"
              type="text"
              value={root}
              onChange={(event) => setRoot(event.target.value)}
              placeholder={t("Optional, e.g. file:///Users/me/research/project")}
              disabled={isSubmitting}
            />
          </label>

          {error && <div className="error-message"><span>{localizeMessage(error)}</span></div>}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose} disabled={isSubmitting}>{t("Cancel")}</button>
          <button 
            className="btn-primary" 
            onClick={handleSubmit}
            disabled={isSubmitting}
          >
            {isSubmitting ? t('Creating...') : t('Create Workspace')}
          </button>
        </div>
      </div>
    </div>
  );
};
