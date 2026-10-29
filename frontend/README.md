# OntoForge Frontend

Electron-based desktop application for visualizing research papers as a matrix grid with integrated evidence inspection.

## Architecture

- **Main Process** (`main.js`): Electron window management and IPC
- **Preload Script** (`preload.js`): Secure bridge between main and renderer
- **Renderer** (`renderer/`): React + TypeScript UI
- **SSP Client** (`renderer/services/ssp_client.ts`): JSON-RPC communication with backend

## Technology Stack

- **Desktop Framework**: Electron 27+
- **Frontend**: React 18 + TypeScript
- **State Management**: Zustand
- **Data Grid**: TanStack Table (React Table v8)
- **Build**: Vite + electron-builder

## Project Structure

```
frontend/
├── main.js                 # Electron main process
├── preload.js              # IPC bridge (secure)
├── vite.config.ts          # Vite configuration
├── tsconfig.json           # TypeScript config
├── package.json            # Dependencies
├── index.html              # HTML entry point
└── renderer/               # React renderer process
    ├── main.tsx            # React entry point
    ├── App.tsx             # Main app component
    ├── index.css           # Global styles
    ├── components/         # React components
    │   ├── MatrixGrid.tsx            # Main data grid
    │   ├── MatrixCell.tsx            # Individual cell
    │   ├── DigitalMicroscope.tsx     # Evidence viewer
    │   ├── EvidencePanel.tsx         # Evidence list
    │   └── ConfidenceIndicator.tsx   # Confidence bar
    └── services/           # Services and utilities
        ├── workspace.ts              # Workspace state (Zustand)
        └── ssp_client.ts             # SSP JSON-RPC client
```

## Development

### Prerequisites

- Node.js 18+ and npm
- Running OntoForge backend (localhost:8765)

### Install Dependencies

```bash
cd frontend
npm install
```

### Run Development Mode

```bash
npm run electron:dev
```

This will:
1. Start Vite dev server on port 5173
2. Launch Electron window
3. Enable hot module reload

### Build for Production

```bash
npm run electron:build
```

## Features (Phase C)

### ✅ Completed

- [x] Electron app shell with window management
- [x] React + TypeScript renderer setup
- [x] Matrix Grid component (papers × metrics)
- [x] Matrix Cell with status indicators
- [x] Digital Microscope evidence viewer
- [x] Evidence Panel with confidence scores
- [x] SSP JSON-RPC client
- [x] Mock data for development
- [x] Zustand state management

### 🚧 In Progress

- [ ] Connect to real backend (currently using mock data)
- [ ] PDF.js integration for PDF rendering
- [ ] Bounding box overlays on PDF crops
- [ ] Real-time conflict notifications
- [ ] Workspace file picker dialog

### 📋 Planned (Phase D+)

- [ ] Graph visualization view
- [ ] HITL correction workflow UI
- [ ] Global Alignment Matrix Editor
- [ ] Git-like merge conflict interface
- [ ] Export to various formats

## Usage

### Load Workspace

1. Click "Load Workspace" button
2. Select workspace directory containing domain-pack.yaml
3. Backend will initialize and load papers

### View Evidence

1. Click any cell in the matrix grid
2. Digital Microscope panel opens below
3. View supporting evidence with confidence scores
4. Click evidence items to see PDF crops (mock for now)

### Status Indicators

- **🟢 Resolved**: Data verified and locked
- **🟡 Pending**: Awaiting review
- **🔴 Conflict**: Multiple contradicting values found
- **🟣 Locked**: Human arbitrator decision (permanent)

## SSP Protocol Integration

The frontend communicates with the backend via JSON-RPC 2.0:

- `textDocument/sspInitialize`: Load workspace
- `textDocument/sspIngest`: Import new papers
- `textDocument/sspRetrieveEvidence`: Get evidence for a cell
- `textDocument/sspResolveConflict`: Resolve contradictions
- `textDocument/sspLockAssertion`: Lock with human decision

See `renderer/services/ssp_client.ts` for implementation.

## Mock Data

Phase C uses mock data for development (`renderer/services/workspace.ts`):

- 3 sample papers (optical networking domain)
- 4 metrics (reconfiguration_delay, cross_talk, spectral_efficiency, reach)
- Randomized cell data with various statuses
- Mock evidence with confidence scores

Replace with real SSP calls when backend is ready.

## Electron Security

- **Context Isolation**: Enabled
- **Node Integration**: Disabled
- **Sandbox**: Enabled
- **Preload Script**: Secure IPC bridge only

## Troubleshooting

### Port 5173 already in use

```bash
# Kill process using port
lsof -ti:5173 | xargs kill -9
```

### Backend connection failed

Ensure backend is running:
```bash
cd ../backend
python3 -m server.app
```

### Electron window blank

Check browser console (F12) for errors. Verify Vite dev server is running.

## License

MIT
