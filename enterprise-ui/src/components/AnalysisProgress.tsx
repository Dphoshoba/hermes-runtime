import { useState } from 'react';

interface AnalysisStep {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'complete' | 'error';
}

interface AnalysisProgressProps {
  projectName: string;
  onComplete: () => void;
}

const STEPS: AnalysisStep[] = [
  { id: 'discover', label: 'Discovering project structure', status: 'pending' },
  { id: 'scan', label: 'Scanning for findings', status: 'pending' },
  { id: 'analyze', label: 'Analyzing findings', status: 'pending' },
  { id: 'summarize', label: 'Preparing summary', status: 'pending' },
];

export default function AnalysisProgress({ projectName, onComplete }: AnalysisProgressProps) {
  const [steps, setSteps] = useState<AnalysisStep[]>(STEPS);
  const [currentStep, setCurrentStep] = useState(0);
  const [progress, setProgress] = useState(0);

  const startAnalysis = () => {
    setProgress(0);
    setCurrentStep(0);
    runStep(0);
  };

  const runStep = (index: number) => {
    if (index >= STEPS.length) {
      setTimeout(onComplete, 500);
      return;
    }
    setCurrentStep(index);
    setSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...s, status: 'running' } : s))
    );
    const interval = setInterval(() => {
      setProgress((p) => {
        if (p >= (index + 1) * 25) {
          clearInterval(interval);
          setSteps((prev) =>
            prev.map((s, i) => (i === index ? { ...s, status: 'complete' } : s))
          );
          setTimeout(() => runStep(index + 1), 300);
          return p;
        }
        return p + 5;
      });
    }, 100);
  };

  const getStepIcon = (status: string) => {
    switch (status) {
      case 'complete': return '✓';
      case 'running': return '◌';
      case 'error': return '✗';
      default: return '○';
    }
  };

  return (
    <div className="analysis-progress">
      <div className="progress-header">
        <h2>Analyzing {projectName}</h2>
        <p className="muted">
          EVOSIA is reviewing your project. This is read-only — no changes are
          being made.
        </p>
      </div>

      <div className="progress-bar-container">
        <div className="progress-bar" style={{ width: `${progress}%` }} />
      </div>

      <div className="steps-list">
        {steps.map((step) => (
          <div key={step.id} className={`step-item ${step.status}`}>
            <span className={`step-icon ${step.status}`}>{getStepIcon(step.status)}</span>
            <span className="step-label">{step.label}</span>
          </div>
        ))}
      </div>

      {currentStep < STEPS.length && (
        <button className="btn btn-primary" onClick={startAnalysis}>
          Start Analysis
        </button>
      )}

      {progress === 100 && (
        <div className="analysis-complete">
          <p>✓ Analysis complete</p>
        </div>
      )}
    </div>
  );
}
