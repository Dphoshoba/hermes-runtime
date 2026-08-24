import { useState } from 'react';

interface PreparedChangeDetail {
  id: string;
  title: string;
  what: string;
  why: string;
  benefit: string;
  risk: string;
  files: string[];
  verification: string;
  rollback: string;
  validation: 'pass' | 'pending' | 'fail';
  status?: string;
  diff?: string | null;
  workspace?: string | null;
  validationOutput?: string | null;
  isLive?: boolean;
  failure_reason?: string | null;
}

interface PreparedChangeViewProps {
  change: PreparedChangeDetail;
  onApprove: () => void;
  onTryAgain?: () => void;
  onExplain?: () => void;
  onReturn?: () => void;
}

export default function PreparedChangeView({
  change,
  onApprove,
  onTryAgain,
  onExplain,
  onReturn,
}: PreparedChangeViewProps) {
  const [showDiff, setShowDiff] = useState(false);
  const isPrepared = change.status === 'PREPARED';
  const isFailed = change.status === 'failed';
  const hasFailureOutput =
    isFailed && (change.validationOutput || change.failure_reason);

  return (
    <div className="prepared-change-card card">
      {isFailed && hasFailureOutput && (
        <div className="failure-banner">
          <h3>Preparation failed</h3>
          <p className="unchanged">Your project was not changed.</p>
          {change.failure_reason && (
            <p className="reason">
              <strong>What happened:</strong> {change.failure_reason}
            </p>
          )}
          {(change.validationOutput || '').split('\n')[0] && (
            <p className="reason">
              <strong>Technical details:</strong>{' '}
              {(change.validationOutput || '').split('\n')[0]}
            </p>
          )}
        </div>
      )}

      {!isFailed && (
        <>
          <h3>{change.title}</h3>
          <span
            className={`badge ${
              isPrepared ? 'badge-amber' : 'badge-yellow'
            }`}
          >
            {isPrepared ? 'Prepared change' : 'Preparation pending'}
          </span>
        </>
      )}

      {isFailed && hasFailureOutput ? (
        <div className="failure-actions">
          <h4>What you can do</h4>
          <div className="action-buttons">
            {onTryAgain && (
              <button className="btn btn-primary" onClick={onTryAgain}>
                Try again
              </button>
            )}
            {onExplain && (
              <button className="btn btn-secondary" onClick={onExplain}>
                Ask EVOSIA to explain
              </button>
            )}
            {onReturn && (
              <button className="btn btn-secondary" onClick={onReturn}>
                Return to recommendation
              </button>
            )}
          </div>
        </div>
      ) : (
        <>
          <div className="change-section">
            <h4>What will change</h4>
            <p>{change.what}</p>
            <div className="change-section">
              <h4>Why</h4>
              <p>{change.why}</p>
            </div>
          </div>
          <div className="change-section">
            <h4>Expected benefit</h4>
            <p>{change.benefit}</p>
          </div>
          <div className="change-section">
            <h4>Possible risk</h4>
            <p>{change.risk}</p>
          </div>
        </>
      )}

      <div className="change-section">
        <h4>Files affected</h4>
        <div className="change-files">
          {change.files.length > 0 ? (
            change.files.map((f, i) => (
              <div key={i} className="change-file">{f}</div>
            ))
          ) : (
            <div className="change-file muted">Not yet determined</div>
          )}
        </div>
      </div>

      <div className="change-section">
        <h4>How it will be verified</h4>
        <p>{change.verification}</p>
      </div>

      <div className="change-section">
        <h4>Validation result</h4>
        <div className={`validation-result ${change.validation}`}>
          {change.validation === 'pass' && '✓ Passed'}
          {change.validation === 'pending' && '⏳ Pending'}
          {change.validation === 'fail' && '✗ Failed'}
        </div>
      </div>

      {isPrepared && !isFailed && (
        <div className="change-section">
          <h4>Isolated workspace</h4>
          <p className="muted">{change.workspace || 'Not recorded'}</p>
          <h4>Candidate diff</h4>
          {change.diff ? (
            <pre className="diff-block">{change.diff}</pre>
          ) : (
            <p className="muted">No diff recorded.</p>
          )}
          <h4>Validation output</h4>
          {change.validationOutput ? (
            <pre className="diff-block">{change.validationOutput}</pre>
          ) : (
            <p className="muted">No validation output recorded.</p>
          )}
        </div>
      )}

      {!isFailed && (
        <div className="change-section">
          <h4>How it can be undone</h4>
          <p>{change.rollback}</p>
        </div>
      )}

      {!isFailed && (
        <div className="authority-statement card highlight">
          <strong>Important:</strong> This change has been{' '}
          <strong>prepared</strong> but has{' '}
          <strong>not been applied</strong> to your project. Approving here
          permits EVOSIA to prepare the change in an isolated workspace. It
          will <strong>not</strong> merge, deploy, or change production.
        </div>
      )}

      {!isFailed && (
        <div className="mission-actions">
          <button className="btn btn-primary" onClick={onApprove}>
            Approve for future execution
          </button>
          <button className="btn btn-sm">Dismiss</button>
          <button
            className="btn btn-sm"
            onClick={() => setShowDiff(!showDiff)}
          >
            {showDiff ? 'Hide' : 'Show'} technical details
          </button>
        </div>
      )}

      {showDiff && !isFailed && (
        <details className="technical-details">
          <summary>Technical details</summary>
          <pre>{JSON.stringify(change, null, 2)}</pre>
        </details>
      )}

      {showDiff && isFailed && hasFailureOutput && (
        <details className="technical-details">
          <summary>Technical details (failure diagnostics)</summary>
          <pre>{JSON.stringify(change, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}