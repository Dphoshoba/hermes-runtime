import { useState } from 'react';
import { useMode } from '../context/ModeContext';

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
    title: 'What EVOSIA does',
    body: 'EVOSIA inspects your project and produces a plain-language summary. It can identify issues worth discussing, ask for context about your project, and recommend work.',
    detail: 'A prepared change is a candidate modification created in an isolated workspace. Prepared ≠ Executed. It is not merged, deployed, or applied to your project until you explicitly choose to act.',
  },
  {
    title: 'Needs your attention',
    body: '"Needs your attention" means EVOSIA found something a human reviewer flagged as worth addressing.',
    detail: 'You decide whether to act on it. EVOSIA will not act without your approval.',
  },
  {
    title: 'Needs context',
    body: '"Needs context" means EVOSIA asks you a question about your project so it can understand your intentions.',
    detail: 'Answering a context question provides information only. It is not authorization and does not permit EVOSIA to change anything.',
  },
  {
    title: 'Proposed work & approval',
    body: '"Proposed work" is a recommendation. Approving preparation permits EVOSIA to prepare a change in an isolated workspace only.',
    detail: 'Preparation does not merge code, deploy anything, or modify your live project. Your project remains unchanged.',
  },
  {
    title: "Let's begin",
    body: 'EVOSIA will now review your project and show you a plain-language summary.',
    detail: "Has EVOSIA changed your project? No. EVOSIA inspects and explains. Nothing is changed unless you approve a prepared change.",
  },
];

export default function FirstRunOnboarding({ onComplete, projectName }: OnboardingProps) {
  const [step, setStep] = useState(0);
  const current = STEPS[step];
  const { isDemo } = useMode();

  return (
    <div className="onboarding-overlay">
      {isDemo && (
        <div className="onboarding-demo-notice">
          <span>Demo mode — sample onboarding only. This is not live EVOSIA evidence.</span>
        </div>
      )}
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
        {isDemo && (
          <div className="onboarding-demo-footer">
            Demo mode — sample onboarding only. Not live EVOSIA evidence.
          </div>
        )}
      </div>
    </div>
  );
}
