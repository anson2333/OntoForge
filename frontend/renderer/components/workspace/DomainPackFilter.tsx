/**
 * Domain Pack Filter Component
 * Multi-select dropdown to filter matrix view by active domain packs
 */

import React, { useState, useRef, useEffect } from 'react';
import { useWorkspaceStore } from '../../services/workspace';
import './DomainPackFilter.css';

export const DomainPackFilter: React.FC = () => {
  const domainPacks = useWorkspaceStore(state => state.domainPacks);
  const activeDomainPacks = useWorkspaceStore(state => state.activeDomainPackNamespaces);
  const setActiveDomainPacks = useWorkspaceStore(state => state.setActiveDomainPacks);
  
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const toggleDomainPack = (namespace: string) => {
    if (activeDomainPacks.includes(namespace)) {
      // Deactivate
      setActiveDomainPacks(activeDomainPacks.filter(ns => ns !== namespace));
    } else {
      // Activate
      setActiveDomainPacks([...activeDomainPacks, namespace]);
    }
  };

  const selectAll = () => {
    setActiveDomainPacks(domainPacks.map(p => p.namespace));
  };

  const deselectAll = () => {
    setActiveDomainPacks([]);
  };

  const getFilterLabel = () => {
    if (activeDomainPacks.length === 0) {
      return 'No domain packs selected';
    } else if (activeDomainPacks.length === domainPacks.length) {
      return `All domain packs (${domainPacks.length})`;
    } else if (activeDomainPacks.length === 1) {
      const pack = domainPacks.find(p => p.namespace === activeDomainPacks[0]);
      return pack ? `${pack.namespace} only` : '1 domain pack';
    } else {
      return `${activeDomainPacks.length} of ${domainPacks.length} domain packs`;
    }
  };

  if (domainPacks.length === 0) {
    return null;
  }

  return (
    <div className="domain-pack-filter" ref={dropdownRef}>
      <div className="filter-label">Active Domain Packs:</div>
      
      <button 
        className="filter-dropdown-trigger"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="filter-display">{getFilterLabel()}</span>
        <span className="dropdown-arrow">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div className="filter-dropdown-menu">
          <div className="dropdown-header">
            <button className="btn-text" onClick={selectAll}>Select All</button>
            <button className="btn-text" onClick={deselectAll}>Clear</button>
          </div>

          <div className="dropdown-options">
            {domainPacks.map(pack => {
              const isActive = activeDomainPacks.includes(pack.namespace);
              return (
                <label 
                  key={pack.namespace} 
                  className={`dropdown-option ${isActive ? 'selected' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={() => toggleDomainPack(pack.namespace)}
                  />
                  <div className="option-content">
                    <span className="option-icon">📦</span>
                    <div className="option-info">
                      <span className="option-name">{pack.config.domain.name}</span>
                      <span className="option-namespace">{pack.namespace}</span>
                    </div>
                    <span className="option-metric-count">
                      {pack.metrics.length} metrics
                    </span>
                  </div>
                </label>
              );
            })}
          </div>

          {activeDomainPacks.length > 0 && (
            <div className="dropdown-footer">
              <span className="active-count">
                {activeDomainPacks.length} active • {' '}
                {domainPacks
                  .filter(p => activeDomainPacks.includes(p.namespace))
                  .reduce((sum, p) => sum + p.metrics.length, 0)} total metrics
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
