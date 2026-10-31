import { t, uiLabel, localizeMessage } from '../../i18n';
import { FormEvent, useEffect, useState } from 'react';
import { sspClient } from '../../services/ssp_client';
import './WorkspaceMembersModal.css';

interface WorkspaceMember {
  user_id: string;
  username?: string | null;
  display_name?: string | null;
  role: 'owner' | 'editor' | 'viewer';
}

interface WorkspaceMembersModalProps {
  workspaceId: string;
  workspaceName: string;
  canManage: boolean;
  onClose: () => void;
}

export function WorkspaceMembersModal({
  workspaceId,
  workspaceName,
  canManage,
  onClose
}: WorkspaceMembersModalProps) {
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [username, setUsername] = useState('');
  const [role, setRole] = useState<'viewer' | 'editor'>('viewer');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadMembers = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await sspClient.listWorkspaceMembers(workspaceId);
      setMembers(response.members || []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Failed to load workspace members"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadMembers();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [workspaceId]);

  const addMember = async (event: FormEvent) => {
    event.preventDefault();
    const candidate = username.trim();
    if (!candidate) return;
    setSubmitting(true);
    setError(null);
    try {
      await sspClient.addWorkspaceMember(workspaceId, candidate, role);
      setUsername('');
      await loadMembers();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Failed to add member"));
    } finally {
      setSubmitting(false);
    }
  };

  const removeMember = async (member: WorkspaceMember) => {
    setSubmitting(true);
    setError(null);
    try {
      await sspClient.removeWorkspaceMember(workspaceId, member.user_id);
      await loadMembers();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Failed to remove member"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="workspace-members-modal" onClick={event => event.stopPropagation()}>
        <header>
          <div><h2>{t("Workspace Access")}</h2><p>{workspaceName}</p></div>
          <button type="button" onClick={onClose} aria-label={t("Close")}>×</button>
        </header>

        <div className="workspace-members-content">
          {canManage && (
            <form className="workspace-member-form" onSubmit={addMember}>
              <label>
                {t("Username")}
                <input value={username} onChange={event => setUsername(event.target.value)} placeholder={t("Registered username")} />
              </label>
              <label>
                {t("Role")}
                <select value={role} onChange={event => setRole(event.target.value as 'viewer' | 'editor')}>
                  <option value="viewer">{t("Viewer")}</option>
                  <option value="editor">{t("Editor")}</option>
                </select>
              </label>
              <button type="submit" disabled={submitting || !username.trim()}>{t("Add")}</button>
            </form>
          )}

          {error && <div className="workspace-members-error" role="alert">{localizeMessage(error)}</div>}
          {loading ? (
            <div className="workspace-members-state">{t("Loading…")}</div>
          ) : (
            <div className="workspace-member-list">
              {members.map(member => (
                <div className="workspace-member-row" key={member.user_id}>
                  <span>
                    <strong>{member.display_name || member.username || member.user_id}</strong>
                    <small>{member.username ? `@${member.username}` : member.user_id}</small>
                  </span>
                  <span className={`workspace-member-role role-${member.role}`}>{uiLabel(member.role)}</span>
                  {canManage && member.role !== 'owner' && (
                    <button type="button" onClick={() => void removeMember(member)} disabled={submitting} aria-label={t('Remove {name}', { name: member.username || member.user_id })}>×</button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
