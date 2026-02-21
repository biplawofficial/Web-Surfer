import { useState, useRef, useEffect } from 'react'
import './App.css'

function App() {
  const [messages, setMessages] = useState([
    { text: 'Hello! How can I help you today?', sender: 'agent' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    const query = input.trim()
    if (!query || loading) return

    setMessages(prev => [...prev, { text: query, sender: 'user' }])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch('http://localhost:8007/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, mode: 1 })
      })
      const data = await response.json()

      let botResponse = JSON.stringify(data)
      if (data.answer) botResponse = data.answer
      else if (data.result) botResponse = data.result
      else if (data.status === 'error') botResponse = 'Error: ' + data.message

      setMessages(prev => [...prev, { text: botResponse, sender: 'agent' }])
    } catch (err) {
      setMessages(prev => [...prev, { text: 'Error: Could not connect to the server.', sender: 'agent' }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') sendMessage()
  }

  return (
    <div className="chat-container">
      <div className="chat-header">Agentic Surfer</div>
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.sender}`}>
            {msg.text}
          </div>
        ))}
        {loading && (
          <div className="message agent">
            <div className="typing-indicator">
              <div className="dot"></div>
              <div className="dot"></div>
              <div className="dot"></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="chat-input-container">
        <input
          type="text"
          className="chat-input"
          placeholder="Type a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          autoComplete="off"
        />
        <button className="send-button" onClick={sendMessage} disabled={loading}>
          Send
        </button>
      </div>
    </div>
  )
}

export default App
