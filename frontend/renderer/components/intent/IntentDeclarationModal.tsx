import { t, uiLabel, localizeMessage } from '../../i18n';
/**
 * Intent Declaration Modal
 * UI for explicit research intent declaration (Section 2.6.2)
 */

import React, { useEffect, useState } from 'react';
import { useWorkspaceStore } from '../../services/workspace';
import { intentService, IntentMetadata, ParsedIntentResult } from '../../services/intent_service';

interface IntentDeclarationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (intent_id: string) => void;
}

export const IntentDeclarationModal: React.FC<IntentDeclarationModalProps> = ({
  isOpen,
  onClose,
  onSuccess
}) => {
  const workspace = useWorkspaceStore();
  const [message, setMessage] = useState('');
  const [parsedIntent, setParsedIntent] = useState<ParsedIntentResult | null>(null);
  const [intentType, setIntentType] = useState<IntentMetadata['intent_type']>('goal');
  const [intentScope, setIntentScope] = useState<IntentMetadata['intent_scope']>('global');
  const [description, setDescription] = useState('');
  const [constraints, setConstraints] = useState('{}');
  const [activeFrom, setActiveFrom] = useState(new Date().toISOString().split('T')[0]);
  const [activeUntil, setActiveUntil] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setMessage('');
    setParsedIntent(null);
    setIntentType('goal');
    setIntentScope('global');
    setDescription('');
    setConstraints('{}');
    setActiveFrom(new Date().toISOString().split('T')[0]);
    setActiveUntil('');
    setIsSubmitting(false);
    setIsParsing(false);
    setError(null);
  }, [isOpen]);

  const applyParsedIntent = (parsedIntent: ParsedIntentResult) => {
    setParsedIntent(parsedIntent);
    setIntentType(parsedIntent.intent_type);
    setIntentScope(parsedIntent.intent_scope);
    setDescription(parsedIntent.description);
    setConstraints(JSON.stringify(parsedIntent.constraints ?? {}, null, 2));
  };

  const handleParseIntent = async () => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage) {
      setError("Enter a freeform intent description before analyzing it.");
      return;
    }

    setError(null);
    setIsParsing(true);

    try {
      const parsedIntent = await intentService.parseUserIntent({
        workspace_id: workspace.currentWorkspaceId,
        user_id: workspace.currentOwnerId,
        message: trimmedMessage,
        owner_id: workspace.currentOwnerId,
        intent_context: workspace.activeIntentBranch?.branch_id,
      });
      applyParsedIntent(parsedIntent);
    } catch (err: any) {
      setError(err.message || 'Failed to analyze intent');
    } finally {
      setIsParsing(false);
    }
  };

  const handleMessageChange = (value: string) => {
    setMessage(value);
    setError(null);
    if (parsedIntent) {
      setParsedIntent(null);
    }
  };

  const parsedConfidence = parsedIntent ? Math.round(parsedIntent.confidence * 100) : null;

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const constraintsObj = JSON.parse(constraints);
      const result = await intentService.declareIntent({
        user_id: workspace.currentOwnerId,
        intent_type: intentType,
        intent_scope: intentScope,
        description,
        constraints: constraintsObj,
        active_from: activeFrom,
        active_until: activeUntil || undefined
      });

      if (onSuccess) {
        onSuccess(result.intent_id);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || t("Failed to declare intent"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="intent-declare-overlay" onClick={onClose}>
      <div
        className="intent-declare-content"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '760px',
          maxWidth: 'calc(100vw - 24px)',
          maxHeight: 'calc(100vh - 24px)'
        }}
      >
        <div className="modal-header">
          <h2>{t("Declare Research Intent")}</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="intent-form">
          <div className="composer-card" style={{ minHeight: parsedIntent ? 180 : 260 }}>
            <div className="composer-header">
              <label htmlFor="intent-message">{t("Intent Message")}</label>
              <span className="composer-hint">{t("Step 1: describe the intent in plain language")}</span>
            </div>
            <textarea
              id="intent-message"
              value={message}
              onChange={(e) => handleMessageChange(e.target.value)}
              placeholder={t("E.g., find most cited papers in the recent 3 years in optical access networks")}
              rows={3}
              className="message-input"
              style={{
                width: '100%',
                minHeight: parsedIntent ? 120 : 200,
                height: '100%',
                display: 'block',
                boxSizing: 'border-box'
              }}
              required
            />
            <div className="composer-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={handleParseIntent}
                disabled={isParsing || isSubmitting}
              >
                {isParsing ? t('Analyzing...') : parsedIntent ? t('Re-analyze') : t('Analyze with LLM')}
              </button>
            </div>
          </div>

          {parsedIntent && (
            <div className="parsed-card">
              <div className="parsed-card-header">
                <div>
                  <h3>{t("Parsed Intent")}</h3>
                  <p>{t("Step 2: review and edit before confirming")}</p>
                </div>
                <div className="parsed-badges">
                  <span className="parsed-badge">{uiLabel(intentType)}</span>
                  <span className="parsed-badge">{uiLabel(intentScope)}</span>
                  <span className="parsed-badge emphasis">{parsedConfidence}%</span>
                </div>
              </div>

              <div className="compact-grid compact-grid-two">
                <div className="form-group compact-group">
                  <label htmlFor="intent-type">{t("Intent Type")}</label>
                  <select
                    id="intent-type"
                    value={intentType}
                    onChange={(e) => setIntentType(e.target.value as any)}
                    required
                  >
                    <option value="correction">{t("Correction")}</option>
                    <option value="preference">{t("Preference")}</option>
                    <option value="priority">{t("Priority")}</option>
                    <option value="constraint">{t("Constraint")}</option>
                    <option value="goal">{t("Goal")}</option>
                  </select>
                </div>

                <div className="form-group compact-group">
                  <label htmlFor="intent-scope">{t("Scope")}</label>
                  <select
                    id="intent-scope"
                    value={intentScope}
                    onChange={(e) => setIntentScope(e.target.value as any)}
                    required
                  >
                    <option value="local">{t("Local")}</option>
                    <option value="pattern">{t("Pattern")}</option>
                    <option value="global">{t("Global")}</option>
                  </select>
                </div>
              </div>

              <div className="form-group compact-group">
                <label htmlFor="description">{t("Description")}</label>
                <textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  required
                />
              </div>

              <div className="form-group compact-group">
                <label htmlFor="constraints">{t("Constraints (JSON)")}</label>
                <textarea
                  id="constraints"
                  value={constraints}
                  onChange={(e) => setConstraints(e.target.value)}
                  rows={4}
                  className="code-input"
                />
              </div>

              <div className="compact-grid compact-grid-two">
                <div className="form-group compact-group">
                  <label htmlFor="active-from">{t("Active From")}</label>
                  <input
                    type="date"
                    id="active-from"
                    value={activeFrom}
                    onChange={(e) => setActiveFrom(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group compact-group">
                  <label htmlFor="active-until">{t("Active Until")}</label>
                  <input
                    type="date"
                    id="active-until"
                    value={activeUntil}
                    onChange={(e) => setActiveUntil(e.target.value)}
                  />
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="error-message">{localizeMessage(error)}</div>
          )}

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>
              {t("Cancel")}
            </button>
            {parsedIntent && (
              <button type="submit" className="btn-primary" disabled={isSubmitting}>
                {isSubmitting ? t("Confirming...") : t("Confirm Intent")}
              </button>
            )}
          </div>
        </form>
      </div>

      <style>{`
        .intent-declare-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.7);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .intent-declare-content {
          background: var(--panel-bg-elevated);
          color: var(--text-primary);
          border-radius: 10px;
          overflow-y: auto;
          box-shadow: 0 4px 20px var(--shadow-color);
          box-sizing: border-box;
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 14px 16px;
          border-bottom: 1px solid var(--border-color);
        }

        .modal-header h2 {
          margin: 0;
          color: var(--text-primary);
          font-size: 16px;
        }

        .close-btn {
          background: none;
          border: none;
          color: var(--text-secondary);
          font-size: 28px;
          cursor: pointer;
          padding: 0;
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .close-btn:hover {
          color: var(--text-primary);
        }

        .intent-form {
          padding: 14px 16px 16px;
        }

        .form-group {
          margin-bottom: 14px;
        }

        .compact-group {
          margin-bottom: 12px;
        }

        .composer-card,
        .parsed-card {
          border: 1px solid var(--border-color);
          background: color-mix(in srgb, var(--panel-bg-elevated) 84%, var(--surface-bg) 16%);
          border-radius: 8px;
          padding: 12px;
          margin-bottom: 12px;
        }

        .composer-card {
          display: flex;
          flex-direction: column;
          width: 100%;
          box-sizing: border-box;
        }

        .composer-header,
        .parsed-card-header {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: flex-start;
          margin-bottom: 10px;
        }

        .composer-header label,
        .parsed-card-header h3 {
          margin: 0;
        }

        .composer-hint,
        .parsed-card-header p {
          color: var(--text-secondary);
          font-size: 11px;
          margin: 2px 0 0;
        }

        .parsed-card-header h3 {
          font-size: 14px;
          color: var(--text-primary);
        }

        .parsed-badges {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
          justify-content: flex-end;
        }

        .parsed-badge {
          padding: 3px 8px;
          border-radius: 999px;
          background: var(--surface-bg-hover);
          color: var(--text-secondary);
          font-size: 11px;
          text-transform: capitalize;
          border: 1px solid var(--border-color);
        }

        .parsed-badge.emphasis {
          color: var(--text-primary);
          border-color: var(--primary-color);
        }

        .compact-grid {
          display: grid;
          gap: 12px;
        }

        .compact-grid-two {
          grid-template-columns: 1fr 1fr;
        }

        .form-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }

        .form-group label {
          display: block;
          color: var(--text-primary);
          margin-bottom: 6px;
          font-weight: 500;
          font-size: 12px;
        }

        .form-group select,
        .form-group input,
        .form-group textarea {
          width: 100%;
          padding: 8px 10px;
          background: var(--input-bg);
          border: 1px solid var(--border-color);
          border-radius: 4px;
          color: var(--text-primary);
          font-size: 13px;
          font-family: inherit;
        }

        .message-input {
          flex: 1;
          height: 100%;
          resize: vertical;
        }

        .code-input {
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
          min-height: 96px;
        }

        .form-group select:focus,
        .form-group input:focus,
        .form-group textarea:focus {
          outline: none;
          border-color: var(--primary-color);
        }

        .help-text {
          display: block;
          color: var(--text-secondary);
          font-size: 11px;
          margin-top: 4px;
        }

        .composer-actions {
          display: flex;
          justify-content: flex-end;
          margin-top: 10px;
          flex-shrink: 0;
        }

        .error-message {
          padding: 10px 12px;
          background: var(--danger-color);
          color: #fff;
          border-radius: 4px;
          margin-bottom: 12px;
          font-size: 13px;
        }

        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
          padding-top: 4px;
        }

        .btn-primary,
        .btn-secondary {
          padding: 8px 14px;
          border-radius: 4px;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          border: none;
          transition: all 0.2s;
        }

        .btn-primary {
          background: var(--primary-color);
          color: var(--primary-text);
        }

        .btn-primary:hover:not(:disabled) {
          background: var(--primary-hover);
        }

        .btn-primary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-secondary {
          background: var(--surface-bg-hover);
          color: var(--text-primary);
        }

        .btn-secondary:hover {
          background: var(--border-strong);
        }

        @media (max-width: 640px) {
          .intent-declare-content {
            width: calc(100vw - 20px);
          }

          .composer-card {
            min-height: 240px;
          }

          .message-input {
            min-height: 160px;
          }

          .compact-grid-two,
          .form-row {
            grid-template-columns: 1fr;
          }

          .parsed-card-header,
          .composer-header {
            flex-direction: column;
          }

          .parsed-badges {
            justify-content: flex-start;
          }
        }
      `}</style>
    </div>
  );
};
