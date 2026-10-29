/**
 * TabBar Component
 * Navigation tabs for switching between Matrix, Graph, and Timeline views
 */

import { ReactNode } from 'react';
import './TabBar.css';

export type TabId = 'matrix' | 'graph' | 'coverage';

interface Tab {
  id: TabId;
  label: string;
  icon?: string;
  disabled?: boolean;
}

interface TabBarProps {
  activeTab: TabId;
  onTabChange: (tabId: TabId) => void;
  title?: string;
  subtitle?: string;
  meta?: string;
  rightContent?: ReactNode;
}

export default function TabBar({ activeTab, onTabChange, title, subtitle, meta, rightContent }: TabBarProps) {
  const tabs: Tab[] = [
    { id: 'graph', label: 'Graph', icon: '🕸️' },
    { id: 'matrix', label: 'Matrix', icon: '📊' },
    { id: 'coverage', label: 'Coverage' },
  ];

  return (
    <div className="tab-bar">
      <div className="tab-bar-main">
        {(title || subtitle || meta) && (
          <div className="tab-bar-context">
            {title && <div className="tab-bar-title">{title}</div>}
            {(subtitle || meta) && (
              <div className="tab-bar-meta">
                {subtitle && <span>{subtitle}</span>}
                {subtitle && meta && <span className="tab-bar-separator">•</span>}
                {meta && <span>{meta}</span>}
              </div>
            )}
          </div>
        )}

        <div className="tab-bar-tabs">
          {tabs.map(tab => (
            <button
              key={tab.id}
              className={`tab ${activeTab === tab.id ? 'active' : ''} ${tab.disabled ? 'disabled' : ''}`}
              onClick={() => !tab.disabled && onTabChange(tab.id)}
              disabled={tab.disabled}
            >
              {tab.icon && <span className="tab-icon">{tab.icon}</span>}
              <span className="tab-label">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {rightContent && <div className="tab-bar-tools">{rightContent}</div>}
    </div>
  );
}
