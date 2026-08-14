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
}

interface PreparedChangeViewProps {
  change: PreparedChangeDetail;
  onApprove: () => void;
}

export default function PreparedChangeView({ change, onApprove }: PreparedChangeViewProps) {
  const [showDiff, setShowDiff] = useState(false);

  return (
    <div className="prepared-change-card card">
      <h3>{change.title}</h3>
      <div className="change-section">
        <h4>What will change</h4>
        <p>{change.what}</p>
      </div>
      <div className="change-section">
        <h4>Why</h4>
        <p>{change.why}</p>
      </div>
      <div className="change-section">
        <h4>Expected benefit</h4>
        <p>{change.benefit}</p>
      </div>
      <div className="change-section">
        <h4>Possible risk</h4>
        <p>{change.risk}</p>
      </div>
      <div className="change-section">
        <h4>Files affected</h4>
        <div className="change-files">
          {change.files.map((f, i) => (
            <div key={i} className="change-file">{f}</div>
          ))}
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
      <div className="change-section">
        <h4>How it can be undone</h4>
        <p>{change.rollback}</p>
      </div>

      <div className="authority-statement card highlight">
        <strong>Important:</strong> This change has been <strong>prepared</strong> but
        has <strong>not been applied</strong> to your project. Approving here permits
        Hermes to prepare the change in an isolated workspace. It will{' '}
        <strong>not</strong> merge, deploy, or change production.
      </div>

      <div className="mission-actions">
        <button className="btn btn-primary" onClick={onApprove}>
          Approve for future execution
        </button>
        <button className="btn btn-sm">Dismiss</button>
        <button className="btn btn-sm" onClick={() => setShowDiff(!showDiff)}>
          {showDiff ? 'Hide' : 'Show'} technical details
        </button>
      </div>

      {showDiff && (
        <details className="technical-details">
          <summary>Technical details</summary>
          <pre>{JSON.stringify(change, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
