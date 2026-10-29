/**
 * Add Domain Pack Modal
 * Allows users to add a domain pack either by:
 * 1. Uploading a domain pack JSON file
 * 2. Bootstrapping from a research proposal text
 */

import React, { useEffect, useState } from 'react';
import { sspClient } from '../../services/ssp_client';
import './AddDomainPackModal.css';

interface AddDomainPackModalProps {
  onClose: () => void;
  onAddDomainPack: (domainPackData: any, source: 'file' | 'bootstrap') => Promise<void>;
}

export const AddDomainPackModal: React.FC<AddDomainPackModalProps> = ({
  onClose,
  onAddDomainPack
}) => {
  const [activeTab, setActiveTab] = useState<'file' | 'bootstrap'>('file');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [proposalText, setProposalText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const validExtensions = ['.json', '.yaml', '.yml'];
      const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
      
      if (validExtensions.includes(fileExtension) || 
          file.type === 'application/json' || 
          file.type === 'application/x-yaml' || 
          file.type === 'text/yaml') {
        setSelectedFile(file);
        setError(null);
      } else {
        setError('Please select a valid YAML (.yaml, .yml) or JSON (.json) file');
        setSelectedFile(null);
      }
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setError(null);

    try {
      const fileContent = await selectedFile.text();
      const fileExtension = selectedFile.name.substring(selectedFile.name.lastIndexOf('.')).toLowerCase();
      
      // Determine format from file extension
      const format = (fileExtension === '.json') ? 'json' : 'yaml';
      
      // Validate using backend validation endpoint (backend will parse the file)
      const validationResult = await sspClient.validateDomainPack({
        content: fileContent,
        format: format
      });

      const { valid, errors, config } = validationResult;
      
      if (!valid) {
        throw new Error(`Domain pack validation failed:\n${errors.join('\n')}`);
      }

      // Validation passed, use the parsed config from backend
      await onAddDomainPack(config, 'file');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load domain pack file');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBootstrap = async () => {
    if (!proposalText.trim()) {
      setError('Please enter a research proposal');
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      // Call backend to bootstrap domain pack from text
      const bootstrappedConfig = await sspClient.bootstrapDomainPack({
        proposal_text: proposalText
      });

      await onAddDomainPack(bootstrappedConfig, 'bootstrap');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to bootstrap domain pack');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSubmit = () => {
    if (activeTab === 'file') {
      handleFileUpload();
    } else {
      handleBootstrap();
    }
  };

  const isSubmitDisabled = 
    isProcessing || 
    (activeTab === 'file' && !selectedFile) ||
    (activeTab === 'bootstrap' && !proposalText.trim());

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="add-domain-pack-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <h2>Add Domain Pack</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {/* Tab Navigation */}
        <div className="tab-navigation">
          <button
            className={`tab-btn ${activeTab === 'file' ? 'active' : ''}`}
            onClick={() => setActiveTab('file')}
          >
            📁 Upload File
          </button>
          <button
            className={`tab-btn ${activeTab === 'bootstrap' ? 'active' : ''}`}
            onClick={() => setActiveTab('bootstrap')}
          >
            ✨ Bootstrap from Proposal
          </button>
        </div>

        {/* Content */}
        <div className="modal-content">
          {activeTab === 'file' ? (
            <div className="file-upload-section">
              <p className="section-description">
                Upload a domain pack configuration file (YAML or JSON format)
              </p>
              
              <div className="file-input-wrapper">
                <input
                  type="file"
                  id="domain-pack-file"
                  accept=".yaml,.yml,.json,application/json,application/x-yaml,text/yaml"
                  onChange={handleFileSelect}
                  disabled={isProcessing}
                />
                <label htmlFor="domain-pack-file" className="file-input-label">
                  {selectedFile ? selectedFile.name : 'Choose file...'}
                </label>
              </div>

              {selectedFile && (
                <div className="file-info">
                  <span className="file-icon">📄</span>
                  <div className="file-details">
                    <div className="file-name">{selectedFile.name}</div>
                    <div className="file-size">
                      {(selectedFile.size / 1024).toFixed(1)} KB
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bootstrap-section">
              <p className="section-description">
                Describe your research domain or proposal. The system will generate a domain pack configuration automatically.
              </p>
              
              <textarea
                className="proposal-input"
                placeholder="Enter your research proposal or domain description here...&#10;&#10;Example: I'm researching quantum network architectures for distributed computing. Key metrics include entanglement fidelity, quantum bit error rate, and decoherence time. The network will use different topologies like star and mesh configurations."
                value={proposalText}
                onChange={(e) => setProposalText(e.target.value)}
                disabled={isProcessing}
                rows={12}
              />

              <div className="bootstrap-note">
                <span className="note-icon">💡</span>
                <span>The AI will analyze your text and extract domain concepts, metrics, and taxonomy structures.</span>
              </div>
            </div>
          )}

          {error && (
            <div className="error-message">
              <span className="error-icon">⚠️</span>
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button 
            className="btn-secondary" 
            onClick={onClose}
            disabled={isProcessing}
          >
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleSubmit}
            disabled={isSubmitDisabled}
          >
            {isProcessing ? (
              <>
                <span className="spinner">⏳</span>
                {activeTab === 'file' ? 'Loading...' : 'Generating...'}
              </>
            ) : (
              activeTab === 'file' ? 'Add Domain Pack' : 'Bootstrap & Add'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
