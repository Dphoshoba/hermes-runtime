import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../App';
import { guidedClient } from '../lib/api';
import PreparedChangeView from '../components/PreparedChangeView';

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
  const [step, setStep] = useState<GuidedStep>('loading');
  const [summary, setSummary] = useState<GuidedSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const s = await guidedClient.summary();
      setSummary(s);
      setStep('summary');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load guided summary');
      setStep('error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

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
        {step === 'mission-decision' && <MissionDecisionView />}
        {step === 'no-action-needed' && <NoActionNeededView onRefresh={fetchSummary} />}
        {step === 'evidence-exhausted' && <EvidenceExhaustedView />}
        {step === 'prepared-change' && <PreparedChangeView />}
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
        <h1>Guided Mode</h1>
        <div className="guided-safety-badge" role="status">
          <span className="safety-dot" aria-hidden="true" />
          <span>0 changes made</span>
        </div>
        <button className="btn btn-sm" onClick={onRefresh}>Refresh</button>
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
  return (
    <div className="guided-summary">
      <div className="summary-hero card">
        <h2>{summary.headline}</h2>
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
      </div>
    </div>
  );
}

function NeedsAttentionView() {
  const [items, setItems] = useState<NeedsAttentionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      <h2>Worth discussing</h2>
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
      <h2>Needs your context</h2>
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

function MissionDecisionView() {
  const [missions, setMissions] = useState<GuidedMission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    try {
      await guidedClient.approvePreparation(missionId, 'operator');
      loadMissions();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to approve preparation');
    }
  };

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error-msg">{error}</p>;
  if (missions.length === 0) return <p>No proposed work right now.</p>;

  return (
    <div className="mission-decision">
      <h2>Proposed work</h2>
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
              <span className={`badge badge-${m.status === 'APPROVED_FOR_FUTURE_EXECUTION' ? 'green' : 'yellow'}`}>
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
            {m.status === 'DRAFT' || m.status === 'NEEDS_REFINEMENT' ? (
              <div className="mission-actions">
                <button className="btn btn-primary" onClick={() => handleApprove(m.mission_id)}>
                  Approve preparation
                </button>
                <button className="btn btn-sm">Not now</button>
                <button className="btn btn-sm">Needs clarification</button>
              </div>
            ) : (
              <p className="muted">Approved for preparation. Nothing executed yet.</p>
            )}
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

function UsabilityTestEntry() {
  const [expanded, setExpanded] = useState(false);
  // Dev-only affordance; does not compromise normal Guided Mode UX
  const isDev = localStorage.getItem('hermes_dev') === '1';
  if (!isDev) return null;

  return (
    <div className="usability-test-entry card" style={{ marginTop: 40 }}>
      <button className="btn btn-sm" onClick={() => setExpanded(!expanded)}>
        Beta Testing Tools
      </button>
      {expanded && (
        <div style={{ marginTop: 16 }}>
          <p className="muted">
            M9 Usability Test — for facilitators running the real-user beta.
          </p>
          <ul>
            <li>
              <a href="/validation/usability/M9_REAL_USER_TEST_PROTOCOL.md">Test Protocol</a>
            </li>
            <li>
              <a href="/validation/usability/M9_FACILITATOR_QUICK_CARD.md">Facilitator Quick Card</a>
            </li>
            <li>
              <a href="/validation/usability/M9_PARTICIPANT_TEMPLATE.json">Participant Template</a>
            </li>
            <li>
              <a href="/validation/usability/M9_RESULTS_SUMMARY_TEMPLATE.json">Results Summary Template</a>
            </li>
          </ul>
          <p className="muted">
            Enable: <code>localStorage.setItem('hermes_dev', '1')</code>
          </p>
        </div>
      )}
    </div>
  );
}

function PreparedChangeFallback() {
  return (
    <div className="prepared-change card">
      <h2>Prepared change</h2>
      <p>Your approved change is ready for review in an isolated workspace.</p>
      <p className="muted">
        Nothing has been merged, deployed, or applied to production.
      </p>
    </div>
  );
}
