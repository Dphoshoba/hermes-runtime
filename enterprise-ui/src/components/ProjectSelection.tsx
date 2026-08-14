import { useState } from 'react';

interface Project {
  id: string;
  name: string;
  path: string;
  lastAnalyzed?: string;
  status: 'ready' | 'needs_setup' | 'error';
}

interface ProjectSelectionProps {
  onSelect: (project: Project) => void;
  onAnalyze: (projectId: string) => void;
}

const SAMPLE_PROJECTS: Project[] = [
  { id: 'demo-web-app', name: 'Demo Web Application', path: '/projects/demo-web-app', status: 'ready', lastAnalyzed: '2026-08-14' },
  { id: 'demo-api', name: 'Demo API Service', path: '/projects/demo-api', status: 'ready' },
  { id: 'demo-mobile', name: 'Demo Mobile App', path: '/projects/demo-mobile', status: 'needs_setup' },
];

export default function ProjectSelection({ onSelect, onAnalyze }: ProjectSelectionProps) {
  const [projects] = useState<Project[]>(SAMPLE_PROJECTS);
  const [selected, setSelected] = useState<Project | null>(null);
  const [showPicker, setShowPicker] = useState(false);

  const handleSelect = (project: Project) => {
    setSelected(project);
    onSelect(project);
  };

  return (
    <div className="project-selection">
      <div className="selection-header">
        <h2>Choose a project</h2>
        <p className="muted">
          Select a project for Hermes to review. Hermes will analyze the project
          and explain what it finds in plain language.
        </p>
      </div>

      <div className="project-list">
        {projects.map((project) => (
          <button
            key={project.id}
            className={`project-card ${selected?.id === project.id ? 'selected' : ''}`}
            onClick={() => handleSelect(project)}
          >
            <div className="project-icon" aria-hidden="true">
              {project.status === 'ready' ? '📁' : project.status === 'needs_setup' ? '⚠️' : '❌'}
            </div>
            <div className="project-info">
              <div className="project-name">{project.name}</div>
              <div className="project-meta">
                {project.lastAnalyzed && <span>Last reviewed: {project.lastAnalyzed}</span>}
                {!project.lastAnalyzed && <span>Not yet reviewed</span>}
              </div>
            </div>
            <div className="project-status">
              {project.status === 'ready' && <span className="badge badge-green">Ready</span>}
              {project.status === 'needs_setup' && <span className="badge badge-yellow">Needs setup</span>}
              {project.status === 'error' && <span className="badge badge-red">Error</span>}
            </div>
          </button>
        ))}
      </div>

      <div className="selection-actions">
        <button
          className="btn btn-primary"
          disabled={!selected || selected.status !== 'ready'}
          onClick={() => selected && onAnalyze(selected.id)}
        >
          Analyze Project
        </button>
        <button
          className="btn btn-sm"
          onClick={() => setShowPicker(!showPicker)}
        >
          Open Folder
        </button>
      </div>

      {showPicker && (
        <div className="folder-picker card">
          <h3>Open a project folder</h3>
          <p className="muted">
            Choose a folder on your computer. Hermes will look for a project
            inside it.
          </p>
          <div className="picker-mock">
            <p className="muted">
              In a full desktop installation, this would open your system's
              folder picker. For now, select a demo project above.
            </p>
          </div>
        </div>
      )}

      {selected && selected.status === 'needs_setup' && (
        <div className="setup-notice card">
          <h3>This project needs setup</h3>
          <p className="muted">
            Hermes couldn't find a recognizable project structure in this folder.
            Make sure it contains source code files.
          </p>
        </div>
      )}
    </div>
  );
}
