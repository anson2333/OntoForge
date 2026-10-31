import { t, uiLabel, localizeMessage, domainTitle } from '../i18n';
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

interface OntologyGapCandidate {
  id: string;
  kind: 'coverage_missing' | 'alignment_or_conflict_issue' | 'research_hypothesis_candidate';
  rule_id: string;
  status: 'candidate' | 'needs_evidence' | 'excluded' | 'retracted';
  claim: string;
  verification_question: string;
  missing_relation?: Record<string, string>;
  supporting_paths: Array<{
    node_ids: string[];
    evidence_ids: string[];
    paper_ids: string[];
  }>;
  unresolved: string[];
  exclusions: string[];
}

interface ResearchGapReport {
  candidates: OntologyGapCandidate[];
  candidate_count: number;
  input_counts: {
    total: number;
    trusted: number;
    excluded_or_unresolved: number;
  };
  scope_statement: string;
}

interface CoverageViewProps {
  workspaceId: string;
  domainPacks: LoadedDomainPack[];
}

function displayName(value: string): string {
  const label = uiLabel(value);
  if (label !== value) return label;
  return value.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase());
}

function verificationQuestion(candidate: OntologyGapCandidate): string {
  if (candidate.rule_id === 'missing_applicable_evaluation_v1' && candidate.missing_relation) {
    return t('Has {model} been evaluated on {setting} under comparable conditions?', {
      model: candidate.missing_relation.model_variant_id || 'unknown model',
      setting: candidate.missing_relation.to || 'unknown setting'
    });
  }
  if (candidate.rule_id === 'component_transfer_question_v1' && candidate.missing_relation) {
    return t('Does {component} retain its measured effect on {setting}?', {
      component: candidate.missing_relation.component_id || 'unknown component',
      setting: candidate.missing_relation.to || 'unknown setting'
    });
  }
  return candidate.verification_question;
}

export default function CoverageView({ workspaceId, domainPacks }: CoverageViewProps) {
  const [namespace, setNamespace] = useState(domainPacks[0]?.namespace || '');
  const [report, setReport] = useState<CoverageReport | null>(null);
  const [researchGaps, setResearchGaps] = useState<ResearchGapReport | null>(null);
  const [includeMachineChecked, setIncludeMachineChecked] = useState(false);
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
    Promise.all([
      sspClient.getCoverageAnalysis({
        workspace_id: workspaceId,
        domain_pack_namespace: namespace,
        gap_limit: 50
      }),
      sspClient.analyzeResearchGaps({
        workspace_id: workspaceId,
        include_machine_checked: includeMachineChecked,
        limit: 50
      })
    ])
      .then(([coverageResponse, gapResponse]) => {
        if (active) {
          setReport(coverageResponse.coverage as CoverageReport);
          setResearchGaps(gapResponse.analysis as ResearchGapReport);
        }
      })
      .catch(reason => {
        if (active) {
          setReport(null);
          setResearchGaps(null);
          setError(reason instanceof Error ? reason.message : t("Coverage analysis failed"));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [workspaceId, namespace, includeMachineChecked, refreshToken]);

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
          <h1>{t("Coverage Analysis")}</h1>
          <p>{t("Method × scenario × metric evidence in the current workspace")}</p>
        </div>
        <div className="coverage-controls">
          <label className="coverage-quality-toggle">
            <input
              type="checkbox"
              checked={includeMachineChecked}
              onChange={event => setIncludeMachineChecked(event.target.checked)}
            />
            <span>{t("Include machine-checked facts")}</span>
          </label>
          <label>
            {t("Domain pack")}
            <select value={namespace} onChange={event => setNamespace(event.target.value)}>
              {domainPacks.map(pack => (
                <option key={pack.namespace} value={pack.namespace}>
                  {domainTitle(pack.config.domain.name)}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={() => setRefreshToken(value => value + 1)} disabled={loading}>
            {t("Refresh")}
          </button>
        </div>
      </header>

      <div className="coverage-content">
        {loading && !report && <div className="coverage-state">{t("Loading coverage…")}</div>}
        {error && <div className="coverage-state coverage-error" role="alert">{localizeMessage(error)}</div>}
        {!loading && !error && domainPacks.length === 0 && (
          <div className="coverage-state">{t("No domain packs are available for this workspace.")}</div>
        )}

        {report && (
          <>
            <section className="coverage-summary" aria-label={t("Coverage summary")}>
              <div><strong>{percentage}%</strong><span>{t("Coverage")}</span></div>
              <div><strong>{report.coverage.covered_cells} / {report.coverage.total_cells}</strong><span>{t("Cells with evidence")}</span></div>
              <div><strong>{evidencePapers}</strong><span>{t("Supporting papers")}</span></div>
              <div><strong>{report.gap_count}</strong><span>{t("Candidate gaps")}</span></div>
            </section>

            <section className="coverage-section">
              <div className="coverage-section-heading">
                <h2>{t("Evidence Matrix")}</h2>
                <span>{report.methods.length} {t("methods ·")} {report.scenarios.length} {t("scenarios ·")} {report.metrics.length} {t("metrics")}</span>
              </div>
              <div className="coverage-table-scroll">
                <table className="coverage-table">
                  <thead>
                    <tr>
                      <th>{t("Method")}</th>
                      <th>{t("Scenario")}</th>
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
                <h2>{t("Evidence-grounded research questions")}</h2>
                <span>{t("Only facts passing the selected quality policy are used")}</span>
              </div>
              {researchGaps && (
                <>
                  <div className="coverage-quality-summary">
                    <span><strong>{researchGaps.input_counts.trusted}</strong> {t("trusted measurements")}</span>
                    <span><strong>{researchGaps.input_counts.excluded_or_unresolved}</strong> {t("excluded or unresolved")}</span>
                    <span><strong>{researchGaps.candidate_count}</strong> {t("explainable candidates")}</span>
                  </div>
                  {researchGaps.candidates.length > 0 ? (
                    <div className="coverage-table-scroll">
                      <table className="coverage-table ontology-gap-table">
                        <thead>
                          <tr>
                            <th>{t("Type")}</th>
                            <th>{t("Rule")}</th>
                            <th>{t("Candidate and verification question")}</th>
                            <th>{t("Supporting paths")}</th>
                            <th>{t("Status")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {researchGaps.candidates.map(candidate => (
                            <tr key={candidate.id}>
                              <td>{t(candidate.kind)}</td>
                              <td><code>{candidate.rule_id}</code></td>
                              <td className="ontology-gap-claim">
                                <strong>{t(candidate.claim)}</strong>
                                <span>{verificationQuestion(candidate)}</span>
                              </td>
                              <td>{candidate.supporting_paths.length} {t("paths")} · {candidate.supporting_paths.reduce((total, path) => total + path.evidence_ids.length, 0)} {t("evidence references")}</td>
                              <td>{t(candidate.status)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="coverage-state">
                      {t("No candidate passed the current evidence quality policy.")}
                    </div>
                  )}
                  <p className="coverage-scope-note">{t("Candidates are limited to this workspace corpus and do not establish global novelty.")}</p>
                </>
              )}
            </section>

            <section className="coverage-section">
              <div className="coverage-section-heading">
                <h2>{t("Coverage-only leads")}</h2>
                <span>{t("Ranked within the imported literature only")}</span>
              </div>
              {report.gaps.length > 0 ? (
                <div className="coverage-table-scroll">
                  <table className="coverage-table gap-table">
                    <thead>
                      <tr><th>{t("Rank")}</th><th>{t("Method")}</th><th>{t("Scenario")}</th><th>{t("Metric")}</th><th>{t("Score")}</th><th>{t("Evidence signals")}</th></tr>
                    </thead>
                    <tbody>
                      {report.gaps.map((gap, index) => (
                        <tr key={`${gap.method}:${gap.scenario}:${gap.metric}`}>
                          <td>{index + 1}</td>
                          <td>{displayName(gap.method)}</td>
                          <td>{displayName(gap.scenario)}</td>
                          <td>{displayName(gap.metric)}</td>
                          <td className="gap-score">{gap.score}</td>
                          <td>{gap.metric_demand} {t("metric ·")} {gap.method_activity} {t("method ·")} {gap.scenario_activity} {t("scenario")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="coverage-state">{t("No uncovered combinations were found.")}</div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
