import { t, uiLabel } from '../../i18n';
/**
 * EvidenceEditor Component
 * Inline editing interface with PDF comparison view
 */

import { useState, useEffect } from 'react';
import { Evidence, EvidenceModification, IntentMetadata } from './types';
import './EvidenceEditor.css';

interface EvidenceEditorProps {
  evidence: Evidence;
  onSave: (modifications: EvidenceModification, metadata: IntentMetadata) => Promise<void>;
  onCancel: () => void;
}

export default function EvidenceEditor({ evidence, onSave, onCancel }: EvidenceEditorProps) {
  const [originalText, setOriginalText] = useState('');
  const [editedText, setEditedText] = useState('');
  const [changeNotes, setChangeNotes] = useState('');
  const [confidenceOverride, setConfidenceOverride] = useState<number>(0.9);
  const [tags, setTags] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [submitForReview, setSubmitForReview] = useState(false);

  // Reset form when evidence changes
  useEffect(() => {
    const text = evidence.type === 'chunk' 
      ? evidence.raw_text || ''
      : evidence.latex_string || '';
    
    setOriginalText(text);
    setEditedText(text);
    setChangeNotes('');
    setTags([]);
    setSubmitForReview(false);
    setIsSaving(false);
  }, [evidence]);

  const hasChanges = editedText.trim() !== originalText.trim();

  const handleSave = async () => {
    // Allow saving if either text changed OR submitting for review
    if (!hasChanges && !submitForReview) {
      alert(t("No changes to save."));
      return;
    }

    setIsSaving(true);
    try {
      const modifications: EvidenceModification = {
        old_text: originalText,
        new_text: editedText,
        change_notes: changeNotes.trim() || undefined
      };

      const metadata: IntentMetadata = {
        intent_type: 'correction',
        intent_scope: 'local',
        confidence_override: confidenceOverride,
        tags: tags.length > 0 ? tags : submitForReview ? ['review_request'] : ['manual_correction']
      };

      await onSave(modifications, metadata);
    } catch (error) {
      console.error('Failed to save:', error);
      alert(t("Failed to save changes. Please try again."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleTag = (tag: string) => {
    if (tags.includes(tag)) {
      setTags(tags.filter(t => t !== tag));
    } else {
      setTags([...tags, tag]);
    }
  };

  const commonTags = [
    'ocr_error',
    'numeric_correction',
    'formula_fix',
    'unit_correction',
    'formatting_fix',
    'missing_text'
  ];

  return (
    <div className="evidence-editor-overlay">
      <div className="evidence-editor-modal">
        {/* Header */}
        <div className="editor-header">
          <h3>
            {t("Editing")} {evidence.type === 'chunk' ? t("Chunk") : t("Formula")} #{evidence.id.split('#')[1]}
          </h3>
          <button className="close-btn" onClick={onCancel}>✕</button>
        </div>

        {/* Content */}
        <div className="editor-content">
          {/* Left: immutable extraction source */}
          <div className="pdf-comparison">
            <h4>{t("Source Evidence")}</h4>
            <div className="pdf-viewer">
              <div className="pdf-placeholder">
                <p>{t("PDF page")} {evidence.bounding_box.page || 'unknown'}</p>
                <p className="pdf-coords">
                  {t("Region:")} {evidence.bounding_box.coordinate_precision === 'page_only' ? t("unavailable (page only)") : evidence.bounding_box.box.join(', ')}
                </p>
                <blockquote className="source-evidence-text">
                  {originalText || t("No extracted source text is available.")}
                </blockquote>
              </div>
            </div>
            <div className="confidence-display">
              <span>{t("Original Confidence:")}</span>
              <span className={`confidence-value ${
                evidence.confidence_score >= 0.9 ? 'high' :
                evidence.confidence_score >= 0.7 ? 'medium' : 'low'
              }`}>
                {(evidence.confidence_score * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Right: Editable Text */}
          <div className="text-editor">
            <h4>{t("Edit Text")}</h4>
            <textarea
              className={evidence.type === 'formula' ? 'formula-editor' : 'chunk-editor'}
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              rows={12}
              placeholder={t('Edit {type} text here...', { type: uiLabel(evidence.type) })}
            />
            
            <div className="editor-metadata">
              <div className="metadata-field">
                <label htmlFor="change-notes">{t("Change Notes (Optional):")}</label>
                <textarea
                  id="change-notes"
                  value={changeNotes}
                  onChange={(e) => setChangeNotes(e.target.value)}
                  rows={3}
                  placeholder={t("Describe what you changed and why...")}
                />
              </div>

              <div className="metadata-field">
                <label htmlFor="confidence-override">{t("Confidence in correction:")}</label>
                <div className="confidence-slider">
                  <input
                    type="range"
                    id="confidence-override"
                    min="0"
                    max="1"
                    step="0.1"
                    value={confidenceOverride}
                    onChange={(e) => setConfidenceOverride(parseFloat(e.target.value))}
                  />
                  <span className="confidence-value">
                    {(confidenceOverride * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              <div className="metadata-field">
                <label>{t("Tags (Optional):")}</label>
                <div className="tag-selector">
                  {commonTags.map(tag => (
                    <button
                      key={tag}
                      className={`tag-btn ${tags.includes(tag) ? 'active' : ''}`}
                      onClick={() => handleToggleTag(tag)}
                    >
                      {uiLabel(tag)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="metadata-field">
                <label>
                  <input
                    type="checkbox"
                    checked={submitForReview}
                    onChange={(e) => setSubmitForReview(e.target.checked)}
                  />
                  {t("Submit for review by another user")}
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="editor-actions">
          <button
            className="action-btn cancel"
            onClick={onCancel}
            disabled={isSaving}
          >
            {t("↶ Cancel")}
          </button>
          <button
            className="action-btn save"
            onClick={handleSave}
            disabled={(!hasChanges && !submitForReview) || isSaving}
          >
            {isSaving ? t("Saving...") : submitForReview ? t("📤 Save & Request Review") : t("✓ Save & Mark Verified")}
          </button>
        </div>

        {/* Change Preview */}
        {hasChanges && (
          <div className="change-preview">
            <h4>{t("Change Preview")}</h4>
            <div className="diff-view">
              <div className="diff-removed">
                <strong>{t("- Original:")}</strong>
                <pre>{originalText}</pre>
              </div>
              <div className="diff-added">
                <strong>{t("+ Edited:")}</strong>
                <pre>{editedText}</pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
