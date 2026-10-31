import { t } from '../../i18n';
/**
 * Intent Metadata Form
 * Capture intent type, scope, and generalization hint during HITL actions
 */

import React, { useState } from 'react';
import { IntentMetadata } from '../../services/intent_service';

interface IntentMetadataFormProps {
  onSave: (metadata: IntentMetadata) => void;
  onCancel?: () => void;
  initialMetadata?: Partial<IntentMetadata>;
  context?: 'conflict_resolution' | 'unit_selection' | 'subdomain_classification';
}

export const IntentMetadataForm: React.FC<IntentMetadataFormProps> = ({
  onSave,
  onCancel,
  initialMetadata = {},
  context
}) => {
  const [intentType, setIntentType] = useState<IntentMetadata['intent_type']>(
    initialMetadata.intent_type || 'preference'
  );
  const [intentScope, setIntentScope] = useState<IntentMetadata['intent_scope']>(
    initialMetadata.intent_scope || 'local'
  );
  const [generalizationHint, setGeneralizationHint] = useState(
    initialMetadata.generalization_hint || ''
  );
  const [confidenceOverride, setConfidenceOverride] = useState<number | undefined>(
    initialMetadata.confidence_override
  );
  const [tags, setTags] = useState<string[]>(initialMetadata.tags || []);
  const [tagInput, setTagInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const metadata: IntentMetadata = {
      intent_type: intentType,
      intent_scope: intentScope,
      generalization_hint: generalizationHint || undefined,
      confidence_override: confidenceOverride,
      tags: tags.length > 0 ? tags : undefined
    };

    onSave(metadata);
  };

  const addTag = () => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      setTags([...tags, tagInput.trim()]);
      setTagInput('');
    }
  };

  const removeTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  };

  const getContextHelp = () => {
    switch (context) {
      case 'conflict_resolution':
        return t("This intent will be captured with your conflict resolution decision.");
      case 'unit_selection':
        return t("This intent will be learned from your unit preference.");
      case 'subdomain_classification':
        return t("This intent will be associated with your subdomain classification.");
      default:
        return t("Capture metadata about this research decision.");
    }
  };

  return (
    <form className="intent-metadata-form" onSubmit={handleSubmit}>
      <div className="form-header">
        <h3>{t("Capture Intent")}</h3>
        <p className="context-help">{getContextHelp()}</p>
      </div>

      <div className="form-body">
        <div className="form-group">
          <label htmlFor="intent-type">
            {t("Intent Type")}
            <span className="required">*</span>
          </label>
          <select
            id="intent-type"
            value={intentType}
            onChange={(e) => setIntentType(e.target.value as any)}
            required
          >
            <option value="correction">{t("Correction - Tactical error fix")}</option>
            <option value="preference">{t("Preference - Context-specific choice")}</option>
            <option value="priority">{t("Priority - Cross-paper pattern")}</option>
            <option value="constraint">{t("Constraint - Absolute rule")}</option>
            <option value="goal">{t("Goal - Strategic objective")}</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="intent-scope">
            {t("Scope")}
            <span className="required">*</span>
          </label>
          <select
            id="intent-scope"
            value={intentScope}
            onChange={(e) => setIntentScope(e.target.value as any)}
            required
          >
            <option value="local">{t("Local - Apply to this paper only")}</option>
            <option value="pattern">{t("Pattern - Generalizable to similar cases")}</option>
            <option value="global">{t("Global - Apply to all future work")}</option>
          </select>
        </div>

        {intentScope !== 'local' && (
          <div className="form-group">
            <label htmlFor="generalization-hint">
              {t("Generalization Hint")}
              <span className="optional">{t("(optional)")}</span>
            </label>
            <textarea
              id="generalization-hint"
              value={generalizationHint}
              onChange={(e) => setGeneralizationHint(e.target.value)}
              placeholder={t("E.g., 'Apply to all WDM networking papers' or 'When comparing bandwidth metrics'")}
              rows={2}
            />
            <small className="help-text">
              {t("Help the AI understand when to apply this pattern")}
            </small>
          </div>
        )}

        <div className="form-group">
          <label htmlFor="confidence-override">
            {t("Confidence Override")}
            <span className="optional">{t("(optional)")}</span>
          </label>
          <div className="confidence-input">
            <input
              type="range"
              id="confidence-override"
              min="0"
              max="1"
              step="0.05"
              value={confidenceOverride ?? 0.8}
              onChange={(e) => setConfidenceOverride(parseFloat(e.target.value))}
            />
            <span className="confidence-value">
              {((confidenceOverride ?? 0.8) * 100).toFixed(0)}%
            </span>
            <button
              type="button"
              className="btn-clear"
              onClick={() => setConfidenceOverride(undefined)}
              title={t("Use default confidence")}
            >
              ✕
            </button>
          </div>
          <small className="help-text">
            {t("Override AI confidence for this decision")}
          </small>
        </div>

        <div className="form-group">
          <label htmlFor="tags">
            {t("Tags")}
            <span className="optional">{t("(optional)")}</span>
          </label>
          <div className="tag-input-container">
            <input
              type="text"
              id="tags"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addTag();
                }
              }}
              placeholder={t("Add tags (press Enter)")}
            />
            <button type="button" className="btn-add-tag" onClick={addTag}>
              {t("Add")}
            </button>
          </div>
          {tags.length > 0 && (
            <div className="tag-list">
              {tags.map((tag) => (
                <span key={tag} className="tag">
                  {tag}
                  <button
                    type="button"
                    className="tag-remove"
                    onClick={() => removeTag(tag)}
                    aria-label={t('Remove {name}', { name: tag })}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="form-footer">
        {onCancel && (
          <button type="button" className="btn-cancel" onClick={onCancel}>
            {t("Skip Intent Capture")}
          </button>
        )}
        <button type="submit" className="btn-save">
          {t("Save Intent")}
        </button>
      </div>

      <style>{`
        .intent-metadata-form {
          background: #2a2a2a;
          border: 1px solid #444;
          border-radius: 6px;
          overflow: hidden;
        }

        .form-header {
          padding: 16px;
          border-bottom: 1px solid #444;
          background: #1e1e1e;
        }

        .form-header h3 {
          margin: 0 0 6px 0;
          color: #fff;
          font-size: 16px;
        }

        .context-help {
          margin: 0;
          color: #888;
          font-size: 12px;
          font-style: italic;
        }

        .form-body {
          padding: 16px;
        }

        .form-group {
          margin-bottom: 20px;
        }

        .form-group:last-child {
          margin-bottom: 0;
        }

        .form-group label {
          display: block;
          color: #ddd;
          margin-bottom: 6px;
          font-weight: 500;
          font-size: 13px;
        }

        .required {
          color: #ff6b6b;
          margin-left: 4px;
        }

        .optional {
          color: #888;
          margin-left: 6px;
          font-weight: 400;
          font-size: 11px;
        }

        .form-group select,
        .form-group input[type="text"],
        .form-group textarea {
          width: 100%;
          padding: 8px 12px;
          background: #1e1e1e;
          border: 1px solid #444;
          border-radius: 4px;
          color: #fff;
          font-size: 13px;
          font-family: inherit;
        }

        .form-group select:focus,
        .form-group input:focus,
        .form-group textarea:focus {
          outline: none;
          border-color: #007acc;
        }

        .help-text {
          display: block;
          color: #666;
          font-size: 11px;
          margin-top: 4px;
        }

        .confidence-input {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .confidence-input input[type="range"] {
          flex: 1;
          height: 4px;
          background: #444;
          border: none;
          border-radius: 2px;
          outline: none;
          cursor: pointer;
        }

        .confidence-input input[type="range"]::-webkit-slider-thumb {
          appearance: none;
          width: 16px;
          height: 16px;
          background: #007acc;
          border-radius: 50%;
          cursor: pointer;
        }

        .confidence-input input[type="range"]::-moz-range-thumb {
          width: 16px;
          height: 16px;
          background: #007acc;
          border-radius: 50%;
          border: none;
          cursor: pointer;
        }

        .confidence-value {
          min-width: 45px;
          color: #007acc;
          font-weight: 600;
          font-size: 14px;
          text-align: right;
        }

        .btn-clear {
          width: 24px;
          height: 24px;
          padding: 0;
          background: #444;
          border: none;
          border-radius: 4px;
          color: #888;
          font-size: 14px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s;
        }

        .btn-clear:hover {
          background: #d73a49;
          color: #fff;
        }

        .tag-input-container {
          display: flex;
          gap: 8px;
        }

        .tag-input-container input {
          flex: 1;
        }

        .btn-add-tag {
          padding: 8px 16px;
          background: #444;
          border: none;
          border-radius: 4px;
          color: #fff;
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          transition: background 0.2s;
        }

        .btn-add-tag:hover {
          background: #555;
        }

        .tag-list {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-top: 8px;
        }

        .tag {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 8px;
          background: #1e3a5f;
          color: #4da6ff;
          border-radius: 4px;
          font-size: 12px;
        }

        .tag-remove {
          background: none;
          border: none;
          color: #4da6ff;
          font-size: 16px;
          line-height: 1;
          cursor: pointer;
          padding: 0;
          margin-left: 2px;
          transition: color 0.2s;
        }

        .tag-remove:hover {
          color: #ff6b6b;
        }

        .form-footer {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
          padding: 16px;
          border-top: 1px solid #444;
          background: #1e1e1e;
        }

        .btn-cancel,
        .btn-save {
          padding: 10px 20px;
          border: none;
          border-radius: 4px;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn-cancel {
          background: #444;
          color: #fff;
        }

        .btn-cancel:hover {
          background: #555;
        }

        .btn-save {
          background: #007acc;
          color: #fff;
        }

        .btn-save:hover {
          background: #005a9e;
        }
      `}</style>
    </form>
  );
};
