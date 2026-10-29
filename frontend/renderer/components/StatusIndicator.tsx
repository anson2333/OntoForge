/**
 * StatusIndicator - Minimal status indicator for services
 * Shows a colored dot with tooltip on hover
 */

interface StatusIndicatorProps {
  status: 'online' | 'offline' | 'degraded' | 'unknown';
  label: string;
  tooltip?: string;
}

export function StatusIndicator({ status, label, tooltip }: StatusIndicatorProps) {
  const getColor = () => {
    switch (status) {
      case 'online':
        return '#10b981'; // green
      case 'degraded':
        return '#f59e0b'; // amber
      case 'offline':
        return '#ef4444'; // red
      case 'unknown':
      default:
        return '#6b7280'; // gray
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'online':
        return 'Online';
      case 'degraded':
        return 'Degraded';
      case 'offline':
        return 'Offline';
      case 'unknown':
      default:
        return 'Unknown';
    }
  };

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        fontSize: '12px',
        cursor: 'default'
      }}
      title={tooltip || `${label}: ${getStatusText()}`}
    >
      <div
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          backgroundColor: getColor(),
          boxShadow: status === 'online' ? `0 0 4px ${getColor()}` : 'none',
          transition: 'all 0.3s ease'
        }}
      />
      <span style={{ opacity: 0.9 }}>{label}</span>
    </div>
  );
}
