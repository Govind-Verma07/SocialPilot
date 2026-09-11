/**
 * src/components/ui/LoadingState.jsx
 * Centered loading indicator with spinner.
 */

import './LoadingState.css'

export default function LoadingState({ message = 'Loading…', size = 'md' }) {
  return (
    <div className={`loading-state size-${size}`}>
      <span className="spinner" />
      <span className="loading-msg">{message}</span>
    </div>
  )
}
