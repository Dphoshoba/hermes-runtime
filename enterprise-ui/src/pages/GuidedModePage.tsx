import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../App';
import { guidedClient } from '../lib/api';
import { buildSha, resolveBuildSha } from '../lib/buildInfo';
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
  repository_metadata: Record<string, unknown> | null;
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
  originating_finding_id: string;
  finding_location: string;
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
        {step === 'needs-attention' && <NeedsAttentionView onNavigate={setStep} />}
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
  const [displaySha, setDisplaySha] = useState(buildSha());
  useEffect(() => {
    resolveBuildSha().then(setDisplaySha);
  }, []);
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
      <footer className="guided-build-footer" title="EVOSIA build identifier">
        EVOSIA build: {displaySha}
      </footer>
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
  const [scope, setScope] = useState<any>(null);
  const [scopeState, setScopeState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let cancelled = false;
    guidedClient
      .reviewScope()
      .then((s) => { if (!cancelled) { setScope(s); setScopeState('ready'); } })
      .catch(() => { if (!cancelled) setScopeState('error'); });
    return () => { cancelled = true; };
  }, []);

  const fmtDate = (iso: string | null) =>
    iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'long', timeStyle: 'short' }) : null;

  const isDisposable = summary.repository_metadata?.is_disposable === true;
  const repositoryUrl = summary.repository_metadata?.local_path as string | undefined;

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
        {isDisposable && (
          <div className="project-source-notice" data-testid="project-source-notice">
            <p><strong>Test project provided for this evaluation.</strong></p>
            <p className="muted">No files on your computer are being accessed.</p>
          </div>
        )}
        {!isDisposable && repositoryUrl && (
          <div className="project-source-notice" data-testid="project-source-notice">
            <p className="muted">Local project: {repositoryUrl}</p>
          </div>
        )}
      </div>

      {/* WHAT I REVIEWED — authoritative review scope */}
      <div className="review-scope card" data-testid="review-scope">
        <h3>What I reviewed</h3>
        {scopeState === 'loading' && <p className="muted">Checking review coverage…</p>}
        {scopeState === 'error' && (
          <p className="muted">
            EVOSIA completed this review, but detailed file coverage could not be loaded right now.
          </p>
        )}
        {scopeState === 'ready' && scope && !scope.available && (
          <p className="muted">{scope.message || 'EVOSIA completed this review, but detailed file coverage was not recorded for this review.'}</p>
        )}
        {scopeState === 'ready' && scope?.available && (
          <>
            <p>
              Review complete{scope.completed_at ? ` · ${fmtDate(scope.completed_at)}` : ''}
            </p>
            <ul className="scope-list">
              <li>Project: <strong>{scope.repository_name || scope.scope_root}</strong></li>
              <li>Folders inspected: <strong>{scope.total_folders_inspected}</strong></li>
              <li>Files inspected: <strong>{scope.total_files_inspected}</strong></li>
              {scope.folders_inspected?.length > 0 && (
                <li>Examples: {scope.folders_inspected.slice(0, 3).map((f: string) => <code key={f}>{f}/</code>)}</li>
              )}
              <li>
                Excluded/skipped:{' '}
                {scope.excluded_files == null
                  ? <>EVOSIA does not have verified exclusion information for this review.</>
                  : <strong>{scope.excluded_files} files</strong>}
              </li>
            </ul>
            <button className="btn btn-sm" onClick={() => setShowAll((v) => !v)}>
              {showAll ? 'Hide full list' : 'See everything reviewed'}
            </button>
            {showAll && scope.files_inspected?.length > 0 && (
              <ul>
                {scope.files_inspected.map((f: string) => <li key={f}><code>{f}</code></li>)}
              </ul>
            )}
            {scope.exclusion_note && <p className="muted">{scope.exclusion_note}</p>}
          </>
        )}
        <p className="muted"><strong>Your project has not been changed.</strong> EVOSIA only inspects and explains.</p>
      </div>

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

      <div className="summary-actions">
        {summary.needs_attention > 0 && (
          <button className="btn btn-primary" onClick={() => onNavigate('needs-attention')}>
            Review important issue
          </button>
        )}
        {summary.needs_context > 0 && (
          <button className="btn" onClick={() => onNavigate('needs-context')}>
            Answer questions ({summary.questions_awaiting_answer})
          </button>
        )}
        {summary.proposed_work > 0 && (
          <button className="btn" onClick={() => onNavigate('mission-decision')}>
            View recommended fixes ({summary.proposed_work})
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

function NeedsAttentionView({ onNavigate }: { onNavigate?: (s: GuidedStep) => void }) {
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
        <h2>What I found</h2>
        <ProvenanceBadge provenance={isDemo ? 'demo' : 'live'} />
      </div>
      <p className="muted">These are items a human reviewer flagged as worth addressing.</p>
      <div className="card-list">
        {items.map((item) => (
          <div key={item.finding_id} className="card attention-card">
            <h3>{item.plain_title}</h3>
            {item.technical?.module != null && (
              <p className="finding-source">Where I found it: <strong>{String(item.technical.module)}</strong></p>
            )}
            <p className="why-matters"><strong>Why this matters:</strong> {item.why_it_matters}</p>
            <div className="card-meta">
              <span className="badge badge-blue">{item.category}</span>
              <span className={`badge badge-${item.severity}`}>{item.severity}</span>
            </div>
            {item.has_human_decision && onNavigate && (
              <button
                className="btn btn-primary"
                onClick={() => onNavigate('mission-decision')}
              >
                Review recommended fix
              </button>
            )}
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
  const [deferred, setDeferred] = useState<Set<string>>(new Set());
  const [clarification, setClarification] = useState<{ missionId: string; text: string; error: boolean } | null>(null);
  const [prepOutcome, setPrepOutcome] = useState<{ missionId: string; status: 'working' | 'success' | 'failed'; message: string } | null>(null);
  const [deferredNotice, setDeferredNotice] = useState(false);
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
    // Duplicate-preparation protection: ignore clicks while a preparation
    // request for this mission is already in flight.
    if (busy === missionId) return;
    setBusy(missionId);
    setPrepOutcome({ missionId, status: 'working', message: 'Preparing a safe preview… Your live project has not been changed.' });
    try {
      const res = await guidedClient.prepareChange(missionId);
      if (res?.status === 'PREPARED') {
        setPrepOutcome({
          missionId,
          status: 'success',
          message:
            'Preparation complete. A candidate change was created in an isolated workspace and validated. Your project has not been changed.',
        });
      } else if (res?.deduplicated) {
        setPrepOutcome({
          missionId,
          status: 'success',
          message: res.message || 'A prepared change already exists for this recommendation. Nothing has been executed.',
        });
      } else {
        const detail = res?.validation_output || res?.message || 'The change could not be prepared.';
        setPrepOutcome({
          missionId,
          status: 'failed',
          message: `Preparation failed. Your project was not changed. What happened: ${detail}`,
        });
      }
    } catch (e: unknown) {
      const detail = e instanceof Error ? e.message : 'Unknown error';
      setPrepOutcome({
        missionId,
        status: 'failed',
        message: `Preparation failed. Your project was not changed. What happened: ${detail}`,
      });
    } finally {
      setBusy(null);
    }
  };

  // "Not now" — truthful local deferral with visible acknowledgement. No
  // approval, no preparation, no repository mutation, no persistence claim.
  const handleDefer = (missionId: string) => {
    setDeferred((prev) => new Set(prev).add(missionId));
    setDeferredNotice(true);
  };

  // "Needs clarification" — uses the governed Gemini explanation layer with
  // visible GEMINI_EXPLANATION provenance and explicit fallback.
  const handleClarify = async (missionId: string) => {
    setBusy(missionId);
    setClarification({ missionId, text: 'Asking EVOSIA for a plain-language explanation…', error: false });
    try {
      const res = await fetch(`/api/guided/explain/mission/${missionId}`, { headers: { Authorization: `Bearer ${localStorage.getItem('evosia_token')}` } });
      if (!res.ok) throw new Error('Explanation unavailable');
      const data = await res.json();
      setClarification({ missionId, text: data.explanation || data.text || 'No explanation available.', error: false });
    } catch {
      setClarification({ missionId, text: 'EVOSIA is unable to load an explanation right now. Based on the review evidence, this recommendation addresses the finding shown above. Please try again later.', error: true });
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error-msg">{error}</p>;
  const visibleMissions = missions.filter((m) => !deferred.has(m.mission_id));

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
      {visibleMissions.length === 0 ? (
        <p>No proposed work right now.</p>
      ) : (
        <div className="card-list">
          {visibleMissions.map((m) => (
            <div key={m.mission_id} className="card mission-card">
              {/* Finding → Recommendation bridge */}
              {m.originating_finding && (
                <div className="mission-source">
                  This recommendation addresses:<br /><strong>{m.originating_finding}</strong>
                </div>
              )}
              {(m.finding_location || m.scope) && (
                <p className="finding-source">Found in: <strong>{m.finding_location || m.scope}</strong></p>
              )}
              <div className="mission-header">
                <h3>{m.plain_title}</h3>
                <span className={`badge badge-${m.status === 'APPROVED_FOR_FUTURE_EXECUTION' ? 'green' : m.status === 'PREPARED' ? 'amber' : 'yellow'}`}>
                  {m.status_label}
                </span>
              </div>
              <div className="mission-body">
                <div className="mission-field"><strong>What:</strong> {m.what}</div>
                <div className="mission-field"><strong>Why:</strong> {m.why}</div>
                <div className="mission-field"><strong>Expected benefit:</strong> {m.benefit}</div>
                <div className="mission-field"><strong>Risk:</strong> {m.risk}</div>
                <div className="mission-field"><strong>What could change:</strong> {m.scope}</div>
                <div className="mission-field"><strong>How EVOSIA would verify:</strong> {m.validation}</div>
                <div className="mission-field"><strong>How to undo:</strong> {m.rollback}</div>
              </div>
              {clarification?.missionId === m.mission_id && (
                <div className={`clarification-panel card ${clarification.error ? 'clarification-error' : ''}`}>
                  <div className="clarification-header">
                    <strong>{clarification.error ? 'EVOSIA explanation' : 'EVOSIA explanation (AI-assisted)'}</strong>
                    <button className="btn btn-sm" onClick={() => setClarification(null)}>Dismiss</button>
                  </div>
                  <p>{clarification.text}</p>
                  {!clarification.error && (
                    <p className="muted provenance-note">This explanation is AI-assisted and is not live EVOSIA evidence.</p>
                  )}
                </div>
              )}
              <div className="authority-statement card highlight">
                <strong>If you approve:</strong> {m.authority_consequence}
              </div>
              {/* Preparation outcome: IDLE → WORKING → SUCCESS/FAILURE */}
              {prepOutcome?.missionId === m.mission_id && (
                <div
                  role="status"
                  className={`prep-outcome card ${prepOutcome.status === 'failed' ? 'prep-failed' : prepOutcome.status === 'success' ? 'prep-success' : ''}`}
                >
                  {prepOutcome.status === 'working' && (
                    <>
                      <strong>Preparing a safe preview…</strong>
                      <p className="muted">Your live project has not been changed.</p>
                    </>
                  )}
                  {prepOutcome.status === 'success' && (
                    <>
                      <strong>Preparation complete</strong>
                      <p>{prepOutcome.message}</p>
                      <p className="muted"><strong>Your live project: UNCHANGED.</strong> Nothing has been merged, deployed, or applied to production.</p>
                      <button className="btn btn-primary" onClick={onPreparedChange}>Review prepared change</button>
                    </>
                  )}
                  {prepOutcome.status === 'failed' && (
                    <>
                      <strong>Preparation failed</strong>
                      <p>{prepOutcome.message}</p>
                      <p className="muted"><strong>Your project was not changed.</strong></p>
                      <div className="prep-actions">
                        <button className="btn btn-primary" onClick={() => handlePrepare(m.mission_id)} disabled={busy === m.mission_id}>Try again</button>
                        <button className="btn btn-sm" onClick={() => handleClarify(m.mission_id)} disabled={busy === m.mission_id}>Ask EVOSIA to explain</button>
                        <button className="btn btn-sm" onClick={() => setPrepOutcome(null)}>Return to recommendation</button>
                      </div>
                      <details className="technical-details">
                        <summary>Technical details</summary>
                        <pre>{m.technical ? JSON.stringify(m.technical, null, 2) : 'No additional diagnostic detail recorded.'}</pre>
                      </details>
                    </>
                  )}
                </div>
              )}
              <div className="mission-actions">
                {m.status === 'DRAFT' || m.status === 'NEEDS_REFINEMENT' ? (
                  <>
                    <button className="btn btn-primary" onClick={() => handleApprove(m.mission_id)} disabled={busy === m.mission_id}>
                      {busy === m.mission_id ? 'Approving…' : 'Approve preparation'}
                    </button>
                    <button className="btn btn-sm" onClick={() => handleDefer(m.mission_id)} disabled={busy === m.mission_id}>Not now</button>
                    <button className="btn btn-sm" onClick={() => handleClarify(m.mission_id)} disabled={busy === m.mission_id}>Needs clarification</button>
                  </>
                ) : m.status === 'APPROVED_FOR_FUTURE_EXECUTION' ? (
                  <>
                    <button className="btn btn-primary" onClick={() => handlePrepare(m.mission_id)} disabled={busy === m.mission_id}>
                      {busy === m.mission_id ? 'Preparing a safe preview…' : 'Prepare safe preview'}
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
      )}
      {deferredNotice && deferred.size > 0 && (
        <div role="status" className="deferred-notice card">
          <p>
            Okay — EVOSIA will leave this recommendation unchanged. You can look at it again any time.{' '}
            <button className="btn btn-sm" onClick={() => { setDeferred(new Set()); setDeferredNotice(false); }}>Show again</button>
          </p>
        </div>
      )}
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

  // Auto-select the latest successful PREPARED change when data loads
  useEffect(() => {
    if (changes.length > 0 && !selected) {
      const latestPrepared = changes.find((c) => c.status === 'PREPARED');
      if (latestPrepared) {
        openDetail(latestPrepared);
      }
    }
  }, [changes, selected]);

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

  // Separate successful and failed changes
  const successfulChanges = changes.filter((c) => c.status === 'PREPARED');
  const failedChanges = changes.filter((c) => c.status !== 'PREPARED');

  // If no successful change exists, show the original flat list for failed changes only
  if (successfulChanges.length === 0 && !selected) {
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
      {(() => {
        const source = selected || successfulChanges[0];
        if (!source) return null;
        // Normalize validation_status: backend returns 'passed'/'failed'/'pending',
        // but PreparedChangeView expects 'pass'/'fail'/'pending'
        const rawValidation = source.validation_status || 'pending';
        const normalizedValidation: 'pass' | 'pending' | 'fail' =
          rawValidation === 'passed' ? 'pass' :
          rawValidation === 'failed' ? 'fail' :
          'pending';
        return (
          <PreparedChangeView
            change={{
              id: source.prepared_id,
              mission_id: source.mission_id,
              title: source.title,
              what: source.description,
              why: 'Based on a human-ACTIONABLE finding approved by an operator.',
              benefit: 'Addresses an operator-flagged engineering concern.',
              risk: 'Change risk depends on scope; prepared changes remain unreviewed until you act.',
              files: source.affected_files || [],
              verification: 'Tests and checks would run before any change is finalized.',
              rollback: 'Prepared changes are isolated and reversible until merged/deployed.',
              validation: normalizedValidation,
              status: (source.status === 'PREPARED' || source.status === 'failed' || source.status === 'pending') ? source.status : 'pending',
              diff: source.diff_content,
              workspace: source.workspace_path,
              validationOutput: source.validation_output,
              isLive: true,
              failure_reason: source.validation_output || 'Validation could not run inside the isolated workspace.',
            }}
            historicalAttempts={failedChanges.map((c) => ({
              id: c.prepared_id,
              status: c.status,
              created_at: c.created_at,
            }))}
            onApprove={() => {}}
            onReturn={() => setSelected(null)}
          />
        );
      })()}
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
