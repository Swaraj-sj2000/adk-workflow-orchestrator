import React from 'react';
import MultiAgentWorkbench from './MultiAgentWorkbench';

export default function AutoPMConsole() {
  return (
    <div className="dashboard">
      <div className="card full-width">
        <h2>Legacy AutoPM Console</h2>
        <div className="alert alert-warning">
          <strong>Legacy Path:</strong> the original AutoPM flow was built around a single service-driven
          simulation path and is no longer the recommended control surface. This page now routes you into
          the new multi-agent workflow so admins use one orchestration model instead of two competing ones.
        </div>
      </div>
      <MultiAgentWorkbench />
    </div>
  );
}
