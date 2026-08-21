import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../App';
import { guidedClient } from '../lib/api';
import { useMode } from '../context/ModeContext';
import ProvenanceBadge from '../components/ProvenanceBadge';
import DemoModeToggle from '../components/DemoModeToggle';
import PreparedChangeView from '../components/PreparedChangeView';
import FirstRunOnboarding from '../components/FirstRunOnboarding';

// Maximum time Guided Mode may show the review spinner before surfacing an
// explicit error. Prevents the indefinite "Reviewing your project…" state
// reported by Participant 1.
const LOADING_TIMEOUT_MS = 30000;

// Types matching the backend guided router responses
interface GuidedSummary {
  repository_id: string | null;
  repository_name: string | null;
  total_findings: number;
  needs_attention: number;
  needs_context: number;
  proposed_work: number;
  important_issue: number;
  questions_awaiting_answer: number;
  authority_level: number;
  authority_level_label: string;
  nothing_changed: boolean;
  headline: string;
  status: string;
}

interface NeedsAttentionItem {
  finding_id: string;
  title: string;
  plain_title: string;
  severity: string;
  category: string;
  why_it_matters: string;
  current_classification: string | null;
  classification_label: string | null;
  has_human_decision: boolean;
  technical: Record<string, unknown>;
}

interface ContextQuestion {
  question_id: string;
  topic: string;
  question: string;
  why_asking: string;
  affects_count: number;
  affects_findings: string[];
  scope: string;
  options: string[];
  technical: Record<string, unknown>;
}

interface GuidedMission {
  mission_id: string;
  title: string;
  plain_title: string;
  what: string;
  why: string;
  benefit: string;
  risk: string;
  scope: string;
  validation: string;
  rollback: string;
  authority_consequence: string;
  status: string;
  status_label: string;
  originating_finding: string;
  human_adjudication_ref: string;
  technical: Record<string, unknown>;
}

interface PreparedChange {
  prepared_id: string;
  mission_id: string;
  title: string;
  description: string;
  status: string;
  affected_files: string[];
  validation_status: string;
  workspace_path: string;
  diff_content: string | null;
  validation_output: string | null;
  created_at: string;
}

type GuidedStep =
  | 'loading'
  | 'summary'
  | 'needs-attention'
  | 'needs-context'
  | 'mission-decision'
  | 'prepared-change'
  | 'no-action-needed'
  | 'evidence-exhausted'
  | 'error';

export default function GuidedModePage() {
  const { } = useAuth();
  const { isOffline } = useMode();
  const [step, setStep] = useState<GuidedStep>('loading');
  const [summary, setSummary] = useState<GuidedSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [onboardingComplete, setOnboardingComplete] = useState(false);
  const loadingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    // Safety net: never leave the spinner running indefinitely. If the
    // request does not resolve within LOADING_TIMEOUT_MS, surface an explicit
    // error instead of leaving the participant stuck at "Reviewing...".
    if (loadingTimerRef.current) clearTimeout(loadingTimerRef.current);
    loadingTimerRef.current = setTimeout(() => {
      setError('EVOSIA is taking longer than expected to review your project. Please try again.');
      setStep('error');
      setLoading(false);
    }, LOADING_TIMEOUT_MS);
    try {
      const s = await guidedClient.summary();
      if (loadingTimerRef.current) clearTimeout(loadingTimerRef.current);
      setSummary(s);
      if (isOffline) {
        setError('EVOSIA is offline. Check your connection and try again.');
        setStep('error');
      } else {
        setStep('summary');
      }
    } catch (e: unknown) {
      if (loadingTimerRef.current) clearTimeout(loadingTimerRef.current);
      setError(e instanceof Error ? e.message : 'Failed to load guided summary');
      setStep('error');
    } finally {
      setLoading(false);
    }
  }, [isOffline]);

  useEffect(() => {
    return () => {
      if (loadingTimerRef.current) clearTimeout(loadingTimerRef.current);
    };
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  // First-run onboarding: show before the summary for first-time participants.
  if (!onboardingComplete) {
    return (
      <FirstRunOnboarding
        onComplete={() => setOnboardingComplete(true)}
        projectName={summary?.repository_name ?? undefined}
      />
    );
  }

  if (loading) {
    return (
      <div className="guided-page">
        <div className="guided-loading">
          <div className="guided-spinner" aria-hidden="true" />
          <p>Reviewing your project…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="guided-page">
        <div className="guided-error card">
          <h2>Something went wrong</h2>
          <p>{error}</p>
          <button className="btn btn-primary" onClick={fetchSummary}>Try again</button>
        </div>
      </div>
    );
  }

  return (
    <div className="guided-page">
      <GuidedLayout
        step={step}
        summary={summary}
        onNavigate={setStep}
        onRefresh={fetchSummary}
      >
        {step === 'summary' && summary && (
          <SummaryView summary={summary} onNavigate={setStep} />
        )}
        {step === 'needs-attention' && <NeedsAttentionView />}
        {step === 'needs-context' && <NeedsContextView />}
        {step === 'mission-decision' && <MissionDecisionView onPreparedChange={() => setStep('prepared-change')} />}
        {step === 'prepared-change' && <PreparedChangeReview onBack={() => setStep('mission-decision')} />}
        {step === 'no-action-needed' && <NoActionNeededView onRefresh={fetchSummary} />}
        {step === 'evidence-exhausted' && <EvidenceExhaustedView />}
      </GuidedLayout>
    </div>
  );
}

function GuidedLayout({
  step,
  summary,
  onNavigate,
  onRefresh,
  children,
}: {
  step: GuidedStep;
  summary: GuidedSummary | null;
  onNavigate: (s: GuidedStep) => void;
  onRefresh: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="guided-layout">
      <header className="guided-header">
        <div className="guided-header-left">
          <h1>Guided Mode</h1>
          {summary && (
            <span className="guided-authority-badge" title={summary.authority_level_label}>
              {summary.authority_level_label}
            </span>
          )}
        </div>
        <div className="guided-header-right">
          <DemoModeToggle />
          <div className="guided-safety-badge" role="status">
            <span className="safety-dot" aria-hidden="true" />
            <span>0 changes made</span>
          </div>
          <button className="btn btn-sm" onClick={onRefresh}>Refresh</button>
        </div>
      </header>

      {summary && (
        <nav className="guided-nav" aria-label="Guided steps">
          <button
            className={`nav-chip ${step === 'summary' ? 'active' : ''}`}
            onClick={() => onNavigate('summary')}
          >
            Overview
          </button>
          <button
            className={`nav-chip ${step === 'needs-attention' ? 'active' : ''}`}
            onClick={() => onNavigate('needs-attention')}
          >
            Needs your attention
            {summary.needs_attention > 0 && <span className="chip-count">{summary.needs_attention}</span>}
          </button>
          <button
            className={`nav-chip ${step === 'needs-context' ? 'active' : ''}`}
            onClick={() => onNavigate('needs-context')}
          >
            Needs context
            {summary.needs_context > 0 && <span className="chip-count">{summary.needs_context}</span>}
          </button>
          <button
            className={`nav-chip ${step === 'mission-decision' ? 'active' : ''}`}
            onClick={() => onNavigate('mission-decision')}
          >
            Proposed work
            {summary.proposed_work > 0 && <span className="chip-count">{summary.proposed_work}</span>}
          </button>
          <button
            className={`nav-chip ${step === 'prepared-change' ? 'active' : ''}`}
            onClick={() => onNavigate('prepared-change')}
          >
            Prepared changes
          </button>
        </nav>
      )}

      <main className="guided-content">{children}</main>
    </div>
  );
}

function SummaryView({
  summary,
  onNavigate,
}: {
  summary: GuidedSummary;
  onNavigate: (s: GuidedStep) => void;
}) {
  const { isDemo } = useMode();

  return (
    <div className="guided-summary">
      <div className="summary-hero card">
        <div className="summary-header-row">
          <h2>{summary.headline}</h2>
          <ProvenanceBadge provenance={isDemo ? 'demo' : 'live'} />
        </div>
        <p className="summary-subtitle">
          {summary.repository_name
            ? `Project: ${summary.repository_name}`
            : 'Your project'}
        </p>
        <div className="summary-stats">
          <div className="summary-stat">
            <div className="stat-number">{summary.total_findings}</div>
            <div className="stat-label">Examined</div>
          </div>
          <div className="summary-stat">
            <div className="stat-number accent">{summary.needs_attention}</div>
            <div className="stat-label">Worth discussing</div>
          </div>
          <div className="summary-stat">
            <div className="stat-number">{summary.questions_awaiting_answer}</div>
            <div className="stat-label">Need your help</div>
          </div>
          <div className="summary-stat">
            <div className="stat-number red">{summary.important_issue}</div>
            <div className="stat-label">Important</div>
          </div>
        </div>
      </div>

      <div className="summary-actions">
        {summary.needs_attention > 0 && (
          <button className="btn btn-primary" onClick={() => onNavigate('needs-attention')}>
            Review items worth discussing
          </button>
        )}
        {summary.needs_context > 0 && (
          <button className="btn" onClick={() => onNavigate('needs-context')}>
            Answer questions ({summary.questions_awaiting_answer})
          </button>
        )}
        {summary.proposed_work > 0 && (
          <button className="btn" onClick={() => onNavigate('mission-decision')}>
            View proposed work ({summary.proposed_work})
          </button>
        )}
        {summary.needs_attention === 0 && summary.needs_context === 0 && summary.proposed_work === 0 && (
          <div className="all-clear card">
            <p>Nothing needs your attention right now.</p>
            <p className="muted">EVOSIA will let you know when something changes.</p>
          </div>
        )}
      </div>

      <div className="authority-info card">
        <h3>What EVOSIA can do right now</h3>
        <ul className="authority-list">
          <li><span className="green">✓</span> Inspect your project</li>
          <li><span className="green">✓</span> Explain findings in plain language</li>
          <li><span className="green">✓</span> Propose work</li>
          <li><span className="muted">○</span> Prepare changes (requires approval)</li>
          <li><span className="red">✗</span> Deploy or execute changes</li>
          <li><span className="red">✗</span> Change production</li>
        </ul>
        <div className="authority-answer">
          <p className="muted">
            <strong>Has EVOSIA changed my project?</strong> No. EVOSIA inspects and explains. Nothing is changed unless you approve a prepared change, and even then it remains in an isolated workspace until you choose to act.
          </p>
        </div>
      </div>
    </div>
  );
}

function NeedsAttentionView() {
  const [items, setItems] = useState<NeedsAttentionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { isDemo } = useMode();

  useEffect(() => {
    guidedClient
      .needsAttention()
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error-msg">{error}</p>;
  if (items.length === 0) return <p>No items need your attention.</p>;

  return (
    <div className="needs-attention">
      <div className="view-header-row">
        <h2>Worth discussing</h2>
        <ProvenanceBadge provenance={isDemo ? 'demo' : 'live'} />
      </div>
      <p className="muted">These are items a human reviewer flagged as worth addressing.</p>
      <div className="card-list">
        {items.map((item) => (
          <div key={item.finding_id} className="card attention-card">
            <h3>{item.plain_title}</h3>
            <p className="why-matters">{item.why_it_matters}</p>
            <div className="card-meta">
              <span className="badge badge-blue">{item.category}</span>
              <span className={`badge badge-${item.severity}`}>{item.severity}</span>
            </div>
            <details className="technical-details">
              <summary>Technical details</summary>
              <pre>{JSON.stringify(item.technical, null, 2)}</pre>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}

function NeedsContextView() {
  const [questions, setQuestions] = useState<ContextQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const { isDemo } = useMode();

  useEffect(() => {
    guidedClient
      .needsContext()
      .then(setQuestions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleAnswer = (qid: string, answer: string) => {
    setAnswers((prev) => ({ ...prev, [qid]: answer }));
  };

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error-msg">{error}</p>;
  if (questions.length === 0) return <p>No questions right now.</p>;

  return (
    <div className="needs-context">
      <div className="view-header-row">
        <h2>Needs your context</h2>
        <ProvenanceBadge provenance={isDemo ? 'demo' : 'live'} />
      </div>
      <p className="muted">
        Your answers help EVOSIA understand your project. EVOSIA will never treat your
        answer as a decision to change code.
      </p>
      <div className="card-list">
        {questions.map((q) => (
          <div key={q.question_id} className="card context-card">
            <h3>{q.topic}</h3>
            <p className="question">{q.question}</p>
            <p className="why-asking muted">{q.why_asking}</p>
            <p className="affects muted">Affects {q.affects_count} finding(s)</p>
            <div className="answer-options">
              {q.options.map((opt) => (
                <button
                  key={opt}
                  className={`answer-btn ${answers[q.question_id] === opt ? 'selected' : ''}`}
                  onClick={() => handleAnswer(q.question_id, opt)}
                >
                  {opt}
                </button>
              ))}
            </div>
            <details className="technical-details">
              <summary>Technical details</summary>
              <pre>{JSON.stringify(q.technical, null, 2)}</pre>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}

function MissionDecisionView({ onPreparedChange }: { onPreparedChange: () => void }) {
  const [missions, setMissions] = useState<GuidedMission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const { isDemo } = useMode();

  const loadMissions = useCallback(() => {
    setLoading(true);
    guidedClient
      .missions()
      .then(setMissions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadMissions();
  }, [loadMissions]);

  const handleApprove = async (missionId: string) => {
    setBusy(missionId);
    try {
      await guidedClient.approvePreparation(missionId, 'operator');
      loadMissions();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to approve preparation');
    } finally {
      setBusy(null);
    }
  };

  const handlePrepare = async (missionId: string) => {
    setBusy(missionId);
    try {
      await guidedClient.prepareChange(missionId);
      onPreparedChange();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to prepare change');
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error-msg">{error}</p>;
  if (missions.length === 0) return <p>No proposed work right now.</p>;

  return (
    <div className="mission-decision">
      <div className="view-header-row">
        <h2>Proposed work</h2>
        <ProvenanceBadge provenance={isDemo ? 'demo' : 'live'} />
      </div>
      <p className="muted">
        These are recommendations based on items you or a reviewer flagged. Approving here
        permits EVOSIA to <strong>prepare</strong> a change in an isolated workspace. It will
        <strong> not</strong> merge, deploy, or change production.
      </p>
      <div className="card-list">
        {missions.map((m) => (
          <div key={m.mission_id} className="card mission-card">
            <div className="mission-header">
              <h3>{m.plain_title}</h3>
              <span className={`badge badge-${m.status === 'APPROVED_FOR_FUTURE_EXECUTION' ? 'green' : m.status === 'PREPARED' ? 'amber' : 'yellow'}`}>
                {m.status_label}
              </span>
            </div>
            <div className="mission-body">
              <div className="mission-field">
                <strong>What:</strong> {m.what}
              </div>
              <div className="mission-field">
                <strong>Why:</strong> {m.why}
              </div>
              <div className="mission-field">
                <strong>Expected benefit:</strong> {m.benefit}
              </div>
              <div className="mission-field">
                <strong>Risk:</strong> {m.risk}
              </div>
              <div className="mission-field">
                <strong>What could change:</strong> {m.scope}
              </div>
              <div className="mission-field">
                <strong>How EVOSIA would verify:</strong> {m.validation}
              </div>
              <div className="mission-field">
                <strong>How to undo:</strong> {m.rollback}
              </div>
            </div>
            <div className="authority-statement card highlight">
              <strong>If you approve:</strong> {m.authority_consequence}
            </div>
            <div className="mission-actions">
              {m.status === 'DRAFT' || m.status === 'NEEDS_REFINEMENT' ? (
                <>
                  <button
                    className="btn btn-primary"
                    onClick={() => handleApprove(m.mission_id)}
                    disabled={busy === m.mission_id}
                  >
                    {busy === m.mission_id ? 'Approving…' : 'Approve preparation'}
                  </button>
                  <button className="btn btn-sm">Not now</button>
                  <button className="btn btn-sm">Needs clarification</button>
                </>
              ) : m.status === 'APPROVED_FOR_FUTURE_EXECUTION' ? (
                <>
                  <button
                    className="btn btn-primary"
                    onClick={() => handlePrepare(m.mission_id)}
                    disabled={busy === m.mission_id}
                  >
                    {busy === m.mission_id ? 'Preparing…' : 'Prepare change'}
                  </button>
                  <p className="muted">Approved for preparation. Nothing executed yet.</p>
                </>
              ) : (
                <p className="muted">Prepared change ready for review.</p>
              )}
            </div>
            <details className="technical-details">
              <summary>Technical details</summary>
              <pre>{JSON.stringify(m.technical, null, 2)}</pre>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}

function PreparedChangeReview({ onBack }: { onBack: () => void }) {
  const [changes, setChanges] = useState<PreparedChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<PreparedChange | null>(null);
  const { isDemo } = useMode();

  useEffect(() => {
    guidedClient
      .preparedChanges()
      .then((data: PreparedChange[]) => setChanges(data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error-msg">{error}</p>;

  if (changes.length === 0) {
    return (
      <div className="no-action card">
        <h2>No prepared changes</h2>
        <p>No changes have been prepared yet. Approve a proposed work item first.</p>
        <button className="btn" onClick={onBack}>Back to proposed work</button>
      </div>
    );
  }

  const openDetail = (c: PreparedChange) => {
    if (isDemo) {
      setSelected(c);
      return;
    }
    // LIVE_MODE: fetch the full record (includes diff/workspace/validation evidence)
    guidedClient
      .getPreparedChange(c.prepared_id)
      .then((full) => setSelected(full))
      .catch(() => setSelected(c));
  };

  if (!selected) {
    return (
      <div className="prepared-change-list">
        <div className="view-header-row">
          <h2>Prepared changes</h2>
          <ProvenanceBadge provenance={isDemo ? 'demo' : 'live'} />
        </div>
        <p className="muted">
          These changes have been prepared in an isolated workspace. Nothing has been
          merged, deployed, or applied to production.
        </p>
        <div className="card-list">
          {changes.map((c) => (
            <button
              key={c.prepared_id}
              className="card prepared-change-card-btn"
              onClick={() => openDetail(c)}
            >
              <h3>{c.title}</h3>
              <p className="muted">{c.description}</p>
              <div className="card-meta">
                <span className={`badge badge-${c.validation_status === 'pass' ? 'green' : c.validation_status === 'pending' ? 'yellow' : 'red'}`}>
                  {c.validation_status}
                </span>
                <span className="muted">Created: {c.created_at}</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="prepared-change-detail">
      <button className="btn btn-sm" onClick={() => setSelected(null)} style={{ marginBottom: 16 }}>
        ← Back to list
      </button>
      <PreparedChangeView
        change={{
          id: selected.prepared_id,
          title: selected.title,
          what: selected.description,
          why: 'Based on a human-ACTIONABLE finding approved by an operator.',
          benefit: 'Addresses an operator-flagged engineering concern.',
          risk: 'Change risk depends on scope; prepared changes remain unreviewed until you act.',
          files: selected.affected_files || [],
          verification: 'Tests and checks would run before any change is finalized.',
          rollback: 'Prepared changes are isolated and reversible until merged/deployed.',
          validation: (selected.validation_status as 'pass' | 'pending' | 'fail') || 'pending',
          status: selected.status,
          diff: selected.diff_content,
          workspace: selected.workspace_path,
          validationOutput: selected.validation_output,
          isLive: !isDemo,
        }}
        onApprove={() => {}}
      />
    </div>
  );
}

function NoActionNeededView({ onRefresh }: { onRefresh: () => void }) {
  return (
    <div className="no-action card">
      <h2>No action needed</h2>
      <p>EVOSIA didn't find anything that needs your attention.</p>
      <button className="btn" onClick={onRefresh}>Check again</button>
    </div>
  );
}

function EvidenceExhaustedView() {
  return (
    <div className="evidence-exhausted card">
      <h2>Evidence exhausted</h2>
      <p>
        EVOSIA has inspected the available evidence and cannot draw firmer conclusions
        without new information.
      </p>
      <p className="muted">
        This may change if new commits, documentation, telemetry, or human context become
        available.
      </p>
    </div>
  );
}
