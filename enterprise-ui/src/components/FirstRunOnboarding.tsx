import { useState } from 'react';

interface OnboardingProps {
  onComplete: () => void;
  projectName?: string;
}

const STEPS = [
  {
    title: 'Welcome to EVOSIA',
    body: 'EVOSIA reviews your software, explains what deserves attention, and can prepare improvements for your approval.',
    detail: 'EVOSIA will not change or deploy your software without additional permission.',
  },
  {
    title: 'What EVOSIA can see',
    body: 'EVOSIA can inspect your project files, dependencies, and structure to identify potential concerns.',
    detail: 'EVOSIA works read-only by default. It does not modify your project unless you explicitly approve a prepared change.',
  },
  {
    title: 'What EVOSIA cannot do',
    body: 'EVOSIA cannot deploy changes, merge code, or modify production systems without additional explicit permission.',
    detail: 'Every action beyond inspection and recommendation requires your clear approval.',
  },
  {
    title: 'When your approval is needed',
    body: 'EVOSIA may ask for context about your project and recommend work. You decide what to prepare.',
    detail: 'No changes are made to your project until you review and approve a prepared change.',
  },
  {
    title: "Let's begin",
    body: 'EVOSIA will now review your project and show you a plain-language summary.',
    detail: "You'll always know exactly what EVOSIA can and cannot do.",
  },
];

export default function FirstRunOnboarding({ onComplete, projectName }: OnboardingProps) {
  const [step, setStep] = useState(0);
  const current = STEPS[step];

  return (
    <div className="onboarding-overlay">
      <div className="onboarding-card">
        <div className="onboarding-progress">
          {STEPS.map((_, i) => (
            <div key={i} className={`progress-dot ${i === step ? 'active' : i < step ? 'done' : ''}`} />
          ))}
        </div>

        <h2>{current.title}</h2>
        <p className="onboarding-body">{current.body}</p>
        <p className="onboarding-detail">{current.detail}</p>

        {projectName && step === STEPS.length - 1 && (
          <p className="onboarding-project">Project: <strong>{projectName}</strong></p>
        )}

        <div className="onboarding-actions">
          {step > 0 && (
            <button className="btn btn-sm" onClick={() => setStep((s) => s - 1)}>
              Back
            </button>
          )}
          {step < STEPS.length - 1 ? (
            <button className="btn btn-primary" onClick={() => setStep((s) => s + 1)}>
              Next
            </button>
          ) : (
            <button className="btn btn-primary" onClick={onComplete}>
              Review my project
            </button>
          )}
          {step < STEPS.length - 1 && (
            <button className="btn btn-sm btn-skip" onClick={onComplete}>
              Skip
            </button>
          )}
        </div>

        <div className="onboarding-safety" role="status">
          <span className="safety-dot" aria-hidden="true" />
          No changes have been made
        </div>
      </div>
    </div>
  );
}
