import { useEffect, useRef } from 'react'

function HomePage({
  siteName,
  hasSource,
  sources,
  messages,
  input,
  onInputChange,
  onSend,
  onOpenModal,
  onClearSources,
  onBackToLanding,
  isBusy,
  onEnterSend,
  onPreviewSource,
  onRemoveSource,
  isDragging
}) {
  const messagesEndRef = useRef(null)
  const messagesContainerRef = useRef(null)

  useEffect(() => {
    const container = messagesContainerRef.current
    if (container) {
      container.scrollTop = container.scrollHeight
    }
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  return (
    <section className="workspace">
      <header className={`topbar ${isDragging ? 'drop-zone' : ''}`}>
        <div className="title-wrap">
          <h2>{siteName} Home</h2>
        </div>
        <div className="topbar-actions">
          <button className="btn primary" onClick={onOpenModal} disabled={isBusy}>
            Add Sources
          </button>
          <button className="btn" onClick={onClearSources} disabled={isBusy}>
            Clear Sources
          </button>
        </div>
      </header>

      <div className="app-grid">
        <aside className={`source-summary ${isDragging ? 'drop-zone' : ''}`}>
          <div className="section-head">
            <h3>Sources</h3>
            <small className="muted">{sources.length}/3</small>
          </div>
          {!hasSource && <p className="muted">No source added yet.</p>}
          <div className="source-list">
            {sources.map((source) => (
              <div className={`source-card ${isDragging ? 'drop-zone' : ''}`} key={source.id}>
                <div className="source-card-head">
                  <div>
                    <strong>{source.name}</strong>
                    <p className="muted">{source.type === 'text' ? 'Pasted text' : 'File source'}</p>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className="badge">{source.type === 'text' ? 'TEXT' : 'FILE'}</span>
                    <button className="btn ghost" onClick={() => onRemoveSource(source.id, source.name)} title="Remove this source">✕</button>
                  </div>
                </div>
                <p className="source-preview">{source.preview}</p>
                {source.previewUrl && (
                  <button className="btn source-preview-btn" onClick={() => onPreviewSource(source)}>
                    Preview file
                  </button>
                )}
              </div>
            ))}
          </div>
          <div className="source-hint">You can keep up to 3 sources at the same time.</div>
        </aside>

        <div className={`chat-box ${isDragging ? 'drop-zone' : ''}`}>
          <div className="section-head">
            <h3>Chat</h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span className="badge online">Ready</span>
              <button className="btn primary" onClick={onOpenModal} disabled={isBusy} style={{ padding: '6px 12px', fontSize: '12px' }}>
                + Add Source
              </button>
            </div>
          </div>

          <div className="messages" ref={messagesContainerRef}>
            {messages.map((msg, index) => (
              <div
                key={msg.id || `${msg.role}-${index}`}
                className={`bubble ${msg.role} ${msg.variant || ''} ${msg.status === 'streaming' ? 'streaming' : ''}`}
              >
                {msg.status === 'typing' ? (
                  <span className="typing-state" aria-label="Assistant is typing">
                    <span className="typing-label">Thinking</span>
                    <span className="typing-dots" aria-hidden="true">
                      <i></i>
                      <i></i>
                      <i></i>
                    </span>
                  </span>
                ) : (
                  <MessageWithCitations text={msg.text} citations={msg.citations || []} />
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="composer">
            <input
              value={input}
              onChange={(event) => onInputChange(event.target.value)}
              placeholder="Upload to get answers"
              aria-label="Question input"
              disabled={isBusy}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  onEnterSend()
                }
              }}
            />
            <button className="btn primary" onClick={onSend} disabled={isBusy}>
              {isBusy ? 'Thinking...' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}

function MessageWithCitations({ text, citations }) {
  if (!text) {
    return null
  }

  const visibleCitations = Array.isArray(citations) ? citations.filter(Boolean).slice(0, 4) : []

  return (
    <div className="message-body">
      <div className="message-text">{text}</div>
      {visibleCitations.length > 0 && (
        <div className="citation-row">
          <span className="citation-label">Citations:</span>
          {visibleCitations.map((citation, index) => (
            <span key={`${index}-${citation.slice(0, 20)}`} className="citation-chip" title={previewCitation(citation)}>
              [{index + 1}]
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function previewCitation(text) {
  const compactText = text.replace(/\s+/g, ' ').trim()
  const sentenceMatch = compactText.match(/^(.+?[.!?])\s/)
  if (sentenceMatch) {
    return sentenceMatch[1]
  }

  return compactText.length > 180 ? `${compactText.slice(0, 180)}...` : compactText
}

export default HomePage
