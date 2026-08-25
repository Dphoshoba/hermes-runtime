import { useState } from 'react';

interface PreparedChangeDetail {
  id: string;
  mission_id: string;
  title: string;
  what: string;
  why: string;
  benefit: string;
  risk: string;
  files: string[];
  verification: string;
  rollback: string;
  validation: 'pass' | 'pending' | 'fail';
  status: 'PREPARED' | 'failed' | 'pending';
  diff?: string | null;
  workspace?: string | null;
  validationOutput?: string | null;
  isLive?: boolean;
  failure_reason?: string | null;
  created_at?: string;
}

interface HistoricalAttempt {
  id: string;
  status: string;
  created_at: string;
}

interface PreparedChangeViewProps {
  change: PreparedChangeDetail;
  historicalAttempts?: HistoricalAttempt[];
  onApprove?: () => void;
  onReturn?: () => void;
}

export default function PreparedChangeView({
  change,
  historicalAttempts = [],
  onApprove,
  onReturn,
}: PreparedChangeViewProps) {
  const [showDiff, setShowDiff] = useState(false);
  const [showValidationDetails, setShowValidationDetails] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const isPrepared = change.status === 'PREPARED';
  const isFailed = change.status === 'failed';
  const hasFailureOutput = isFailed && (change.validationOutput || change.failure_reason);

  return (
    <div className="prepared-change-container">
      {/* === SUCCESS STATE === */}
      {isPrepared && (
        <>
          <header className="prepared-header">
            <h2 className="prepared-title">
              <span className="status-badge prepared-badge">✓ Preparation complete</span>
            </h2>
            <p className="prepared-subtitle">
              EVOSIA prepared a proposed fix for: <strong>{change.title}</strong>
            </p>
          </header>

          <section className="prepared-section">
            <h3>What EVOSIA prepared</h3>
            <p className="plain-explanation">{change.what}</p>

            <div className="prepared-section">
              <h3>Where</h3>
              <div className="affected-files">
                {change.files && change.files.length > 0 ? (
                  change.files.map((f, i) => (
                    <div key={i} className="file-path">{f}</div>
                  ))
                ) : (
                  <span className="file-path muted">File not yet determined</span>
                )}
              </div>
            </div>

            <div className="prepared-section">
              <h3>What would change</h3>
              <p className="before-after-concept">
                Before: the API key value is stored directly in the source file.<br />
                Prepared version: the application reads the value from environment configuration instead.
              </p>
            </div>

            <div className="prepared-section">
              <h3>Checks</h3>
              <div className="validation-summary">
                {change.validation === 'pass' && (
                  <>
                    <span className="validation-pass">✓ Validation passed</span>
                    {(() => {
                      // Extract count from validationOutput if pattern matches "N passed"
                      const match = change.validationOutput?.match(/(\d+)\s+passed/);
                      if (match) {
                        return <span className="validation-count">{match[1]} checks passed successfully.</span>;
                      }
                      return <span className="validation-count">Validation passed successfully.</span>;
                    })()}
                    <button 
                      className="toggle-details"
                      onClick={() => setShowValidationDetails(!showValidationDetails)}
                    >
                      {showValidationDetails ? 'Hide' : 'View'} technical validation details
                    </button>
                    {showValidationDetails && (
                      <details className="validation-details">
                        <summary>Technical validation output</summary>
                        <pre className="validation-output">
                          {change.validationOutput || 'Validation passed'}
                        </pre>
                      </details>
                    )}
                  </>
                )}
                {change.validation === 'pending' && '⏳ Pending'}
                {change.validation === 'fail' && '✗ Failed'}
              </div>
            </div>

            <section className="project-status-section">
              <h3>Your live project: UNCHANGED</h3>
              <p className="unchanged-statement">
                This change exists only in EVOSIA's isolated preparation workspace. Nothing has been merged, deployed, or applied to your project.
              </p>
            </section>

            {change.diff && (
              <div className="prepared-section">
                <h3>Candidate diff</h3>
                <button 
                  className="toggle-diff"
                  onClick={() => setShowDiff(!showDiff)}
                >
                  {showDiff ? 'Hide' : 'View'} technical diff
                </button>
                {showDiff && (
                  <pre className="diff-block">{change.diff}</pre>
                )}
              </div>
            )}

            <div className="authority-statement">
              <strong>EVOSIA has prepared this change for review. It has not applied it.</strong>
            </div>
          </section>

          <div className="prepared-actions">
            <button className="btn btn-primary review-btn" onClick={() => setShowDiff(true)}>
              Review prepared change
            </button>
            {onReturn && (
              <button className="btn btn-secondary" onClick={onReturn}>
                Back to prepared changes
              </button>
            )}
          </div>
        </>
      )}

      {/* === FAILED STATE === */}
      {isFailed && hasFailureOutput && (
        <>
          <header className="failed-header">
            <h2 className="failed-title">
              <span className="status-badge failed-badge">✗ Preparation failed</span>
            </h2>
          </header>

          <section className="failed-section">
            <p className="unchanged-statement">Your project was not changed.</p>

            <div className="failure-details">
              <p><strong>What happened:</strong> {change.failure_reason}</p>
              {change.validationOutput && (
                <p><strong>Technical details:</strong> {change.validationOutput.split('\n')[0]}</p>
              )}
            </div>
          </section>

          <div className="failed-actions">
            {onApprove && (
              <button className="btn btn-primary" onClick={onApprove}>
                Try again
              </button>
            )}
            <button className="btn btn-secondary">
              Ask EVOSIA to explain
            </button>
            {onReturn && (
              <button className="btn btn-secondary" onClick={onReturn}>
                Return to recommendation
              </button>
            )}
          </div>
        </>
      )}

      {/* === NO PREPARATION === */}
      {!isPrepared && !isFailed && (
        <div className="no-preparation">
          <h2>{change.title}</h2>
          <p>Ready for preparation.</p>
          {onApprove && (
            <button className="btn btn-primary" onClick={onApprove}>
              Prepare safe preview
            </button>
          )}
        </div>
      )}

      {/* === HISTORICAL ATTEMPTS === */}
      {historicalAttempts && historicalAttempts.length > 0 && (
        <section className="historical-section">
          <h3>
            <button 
              className="history-toggle"
              onClick={() => setShowHistory(!showHistory)}
            >
              {historicalAttempts.length} previous attempt{ historicalAttempts.length > 1 ? 's' : ''}
              <span className={`chevron ${showHistory ? 'rotated' : ''}`}>▼</span>
            </button>
          </h3>
          
            {showHistory && (
            <div className="history-list">
              {historicalAttempts.map((attempt) => (
                <div key={attempt.id} className="history-item">
                  <div className="history-header">
                    <span className="history-status">
                      {attempt.status === 'failed' ? '✗' : '⏳'} Previous attempt — {attempt.status}
                    </span>
                    {attempt.created_at && (
                      <span className="history-date">{attempt.created_at}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}