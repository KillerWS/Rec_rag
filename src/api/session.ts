let currentSessionId: string | null = null;
let currentConversationMode: 'none' | 'scripted' | 'agent' = 'none';
const modeToSessionId: Record<string, string> = {};

export function getConversationMode(): 'none' | 'scripted' | 'agent' {
  return currentConversationMode;
}

export function setConversationMode(mode: 'none' | 'scripted' | 'agent') {
  currentConversationMode = mode;
  // Initialize a session id for this mode if missing
  if (!modeToSessionId[mode]) {
    const id = (globalThis.crypto && 'randomUUID' in globalThis.crypto)
      ? (globalThis.crypto as any).randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}-${mode}`;
    modeToSessionId[mode] = id;
  }
  // Maintain backward-compatible currentSessionId pointing to active mode id
  currentSessionId = modeToSessionId[mode];
}

export function getSessionId(): string | null {
  // Return the session id for current mode if available
  if (modeToSessionId[currentConversationMode]) {
    return modeToSessionId[currentConversationMode];
  }
  return currentSessionId;
}

export function setSessionId(id: string | null) {
  // Set for current mode; keep legacy field in sync
  if (id != null) {
    modeToSessionId[currentConversationMode] = id as string;
    currentSessionId = id;
    try { sessionStorage.setItem('study_session_id', String(id)); } catch {}
  } else {
    currentSessionId = null;
  }
}

export function ensureSessionId(): string {
  // Prefer persisted study session id if present
  try {
    const persisted = sessionStorage.getItem('study_session_id');
    if (persisted) {
      currentSessionId = persisted;
      if (!modeToSessionId[currentConversationMode]) {
        modeToSessionId[currentConversationMode] = persisted;
      }
      return persisted;
    }
  } catch {}
  // Ensure per-mode id exists; fallback to legacy if needed
  const existing = modeToSessionId[currentConversationMode];
  if (existing) {
    currentSessionId = existing;
    return existing;
  }
  if (!currentSessionId) {
    const id = (globalThis.crypto && 'randomUUID' in globalThis.crypto)
      ? (globalThis.crypto as any).randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    currentSessionId = id;
  }
  // Bind legacy id to current mode to avoid "default" reuse
  modeToSessionId[currentConversationMode] = currentSessionId as string;
  return currentSessionId as string;
} 