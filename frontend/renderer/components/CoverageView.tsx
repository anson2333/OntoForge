import { useEffect, useMemo, useState } from 'react';
import { LoadedDomainPack } from '../services/workspace';
import { sspClient } from '../services/ssp_client';
import './CoverageView.css';

interface CoverageCell {
  count: number;
  assertion_ids: string[];
  paper_ids: string[];
}

interface CoverageRow {
  method: string;
  scenario: string;
  cells: Record<string, CoverageCell>;
}

interface GapCandidate {
  method: string;
  scenario: string;
  metric: string;
  score: number;
  metric_demand: number;
  method_activity: number;
  scenario_activity: number;
}

interface CoverageReport {
  metrics: string[];
  methods: string[];
  scenarios: string[];
  matrix: CoverageRow[];
  coverage: {
    covered_cells: number;
    total_cells: number;
    ratio: number;
  };
  gaps: GapCandidate[];
  gap_count: number;
}

interface CoverageViewProps {
  workspaceId: string;
  domainPacks: LoadedDomainPack[];
}

function displayName(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase());
}

export default function CoverageView({ workspaceId, domainPacks }: CoverageViewProps) {
  const [namespace, setNamespace] = useState(domainPacks[0]?.namespace || '');
  const [report, setReport] = useState<CoverageReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    if (namespace && domainPacks.some(pack => pack.namespace === namespace)) return;
    setNamespace(domainPacks[0]?.namespace || '');
  }, [domainPacks, namespace]);

  useEffect(() => {
    let active = true;
    if (!workspaceId || !namespace) {
      setReport(null);
      return () => { active = false; };
    }

    setLoading(true);
    setError(null);
    sspClient.getCoverageAnalysis({
      workspace_id: workspaceId,
      domain_pack_namespace: namespace,
      gap_limit: 50
    })
      .then(response => {
        if (active) setReport(response.coverage as CoverageReport);
      })
      .catch(reason => {
        if (active) {
          setReport(null);
          setError(reason instanceof Error ? reason.message : 'Coverage analysis failed');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [workspaceId, namespace, refreshToken]);

  const percentage = report ? Math.round(report.coverage.ratio * 100) : 0;
  const evidencePapers = useMemo(() => {
    if (!report) return 0;
    const paperIds = new Set<string>();
    report.matrix.forEach(row => {
      Object.values(row.cells).forEach(cell => cell.paper_ids.forEach(id => paperIds.add(id)));
    });
    return paperIds.size;
  }, [report]);

  return (
    <div className="coverage-view">
      <header className="coverage-header">
        <div>
          <h1>Coverage Analysis</h1>
          <p>Method × scenario × metric evidence in the current workspace</p>
        </div>
        <div className="coverage-controls">
          <label>
            Domain pack
            <select value={namespace} onChange={event => setNamespace(event.target.value)}>
              {domainPacks.map(pack => (
                <option key={pack.namespace} value={pack.namespace}>
                  {pack.config.domain.name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={() => setRefreshToken(value => value + 1)} disabled={loading}>
            Refresh
          </button>
        </div>
      </header>

      <div className="coverage-content">
        {loading && !report && <div className="coverage-state">Loading coverage…</div>}
        {error && <div className="coverage-state coverage-error" role="alert">{error}</div>}
        {!loading && !error && domainPacks.length === 0 && (
          <div className="coverage-state">No domain packs are available for this workspace.</div>
        )}

        {report && (
          <>
            <section className="coverage-summary" aria-label="Coverage summary">
              <div><strong>{percentage}%</strong><span>Coverage</span></div>
              <div><strong>{report.coverage.covered_cells} / {report.coverage.total_cells}</strong><span>Cells with evidence</span></div>
              <div><strong>{evidencePapers}</strong><span>Supporting papers</span></div>
              <div><strong>{report.gap_count}</strong><span>Candidate gaps</span></div>
            </section>

            <section className="coverage-section">
              <div className="coverage-section-heading">
                <h2>Evidence Matrix</h2>
                <span>{report.methods.length} methods · {report.scenarios.length} scenarios · {report.metrics.length} metrics</span>
              </div>
              <div className="coverage-table-scroll">
                <table className="coverage-table">
                  <thead>
                    <tr>
                      <th>Method</th>
                      <th>Scenario</th>
                      {report.metrics.map(metric => <th key={metric}>{displayName(metric)}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {report.matrix.map(row => (
                      <tr key={`${row.method}:${row.scenario}`}>
                        <th>{displayName(row.method)}</th>
                        <td>{displayName(row.scenario)}</td>
                        {report.metrics.map(metric => {
                          const cell = row.cells[metric];
                          return (
                            <td key={metric} className={cell?.count ? 'covered' : 'uncovered'}>
                              {cell?.count || '—'}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="coverage-section">
              <div className="coverage-section-heading">
                <h2>Candidate Gaps</h2>
                <span>Ranked within the imported literature only</span>
              </div>
              {report.gaps.length > 0 ? (
                <div className="coverage-table-scroll">
                  <table className="coverage-table gap-table">
                    <thead>
                      <tr><th>Rank</th><th>Method</th><th>Scenario</th><th>Metric</th><th>Score</th><th>Evidence signals</th></tr>
                    </thead>
                    <tbody>
                      {report.gaps.map((gap, index) => (
                        <tr key={`${gap.method}:${gap.scenario}:${gap.metric}`}>
                          <td>{index + 1}</td>
                          <td>{displayName(gap.method)}</td>
                          <td>{displayName(gap.scenario)}</td>
                          <td>{displayName(gap.metric)}</td>
                          <td className="gap-score">{gap.score}</td>
                          <td>{gap.metric_demand} metric · {gap.method_activity} method · {gap.scenario_activity} scenario</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="coverage-state">No uncovered combinations were found.</div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
