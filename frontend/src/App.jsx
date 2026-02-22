import { useState, useEffect, useRef } from "react";
import "./App.css";

function App() {
  const [userName, setUserName] = useState(
    localStorage.getItem("userName") || ""
  );
  const [tempName, setTempName] = useState("");

  const [theme, setTheme] = useState(
    localStorage.getItem("theme") || "dark"
  );

  const [chats, setChats] = useState(
    JSON.parse(localStorage.getItem("chats")) || []
  );

  const [currentChatId, setCurrentChatId] = useState(null);
  const [message, setMessage] = useState("");
  const [mode, setMode] = useState("normal");
  const [loading, setLoading] = useState(false);

  const textareaRef = useRef(null);
  const chatEndRef = useRef(null);

  // Theme effect
  useEffect(() => {
    document.body.className = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  // Save chats
  useEffect(() => {
    localStorage.setItem("chats", JSON.stringify(chats));
  }, [chats]);

  // Auto scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chats]);

  const createNewChat = (firstMessage = "") => {
    const newChat = {
      id: Date.now(),
      title: firstMessage ? firstMessage.slice(0, 25) : "New Chat",
      messages: []
    };

    setChats(prev => [...prev, newChat]);
    setCurrentChatId(newChat.id);
    return newChat.id;
  };

  const deleteChat = (id) => {
    const filtered = chats.filter(chat => chat.id !== id);
    setChats(filtered);
    setCurrentChatId(filtered.length ? filtered[0].id : null);
  };

  const handleSend = async () => {
    if (!message.trim()) return;

    let activeChatId = currentChatId;

    if (!activeChatId) {
      activeChatId = createNewChat(message);
    }

    const userMessage = message;
    setMessage("");
    setLoading(true);

    // Add user message
    setChats(prev =>
      prev.map(chat =>
        chat.id === activeChatId
          ? {
              ...chat,
              messages: [...chat.messages, { role: "user", text: userMessage }]
            }
          : chat
      )
    );

    const currentChat = chats.find(chat => chat.id === activeChatId);

    const conversation =
      (currentChat?.messages || [])
        .map(m => `${m.role === "user" ? "User" : "AI"}: ${m.text}`)
        .join("\n") +
      `\nUser: ${userMessage}\nAI:`;

    const response = await fetch("http://127.0.0.1:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: conversation,
        model: "llama3",
        temperature: 0.7,
        mode: mode
      })
    });

    if (!response.body) {
      setLoading(false);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let aiText = "";

    // Insert empty AI message
    setChats(prev =>
      prev.map(chat =>
        chat.id === activeChatId
          ? {
              ...chat,
              messages: [...chat.messages, { role: "ai", text: "" }]
            }
          : chat
      )
    );

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      aiText += decoder.decode(value);

      setChats(prev =>
        prev.map(chat => {
          if (chat.id !== activeChatId) return chat;

          const updatedMessages = [...chat.messages];
          updatedMessages[updatedMessages.length - 1] = {
            role: "ai",
            text: aiText
          };

          return { ...chat, messages: updatedMessages };
        })
      );
    }

    setLoading(false);
  };

  // First-time username screen
  if (!userName) {
    return (
      <div className="name-screen">
        <h1>Welcome 👋</h1>
        <input
          placeholder="Enter your name..."
          value={tempName}
          onChange={(e) => setTempName(e.target.value)}
        />
        <button
          onClick={() => {
            localStorage.setItem("userName", tempName);
            setUserName(tempName);
          }}
        >
          Start
        </button>
      </div>
    );
  }

  const currentChat = chats.find(chat => chat.id === currentChatId);

  return (
    <div className="app-container">

      {/* Sidebar */}
      <div className="sidebar">
        <h2>🔥 Personal AI</h2>

        <button onClick={() => createNewChat()}>
          + New Chat
        </button>

        <button
          onClick={() =>
            setTheme(theme === "dark" ? "light" : "dark")
          }
        >
          Toggle Theme
        </button>

        {chats.map(chat => (
          <div
            key={chat.id}
            className={`chat-item ${
              chat.id === currentChatId ? "active" : ""
            }`}
            onClick={() => setCurrentChatId(chat.id)}
          >
            <span>{chat.title}</span>
            <span onClick={() => deleteChat(chat.id)}>🗑</span>
          </div>
        ))}
      </div>

      {/* Main */}
      <div className="main">

        {!currentChat && (
          <div className="greeting">
            <h1>Hello, {userName} 👋</h1>
            <p>Start a new conversation</p>
          </div>
        )}

        {currentChat && (
          <div className="chat-area">
            {currentChat.messages.map((msg, i) => (
              <div
                key={i}
                className={
                  msg.role === "user" ? "user-msg" : "ai-msg"
                }
              >
                {msg.text}
              </div>
            ))}
            {loading && (
              <div className="ai-msg typing">Typing...</div>
            )}
            <div ref={chatEndRef} />
          </div>
        )}

        <div className="input-area">
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="normal">Normal</option>
            <option value="short">Short</option>
            <option value="teacher">Teacher</option>
            <option value="coder">Coder</option>
          </select>

          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height =
                e.target.scrollHeight + "px";
            }}
            placeholder="Type message..."
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
              if (e.key === "Enter" && e.ctrlKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />

          <button
            onClick={handleSend}
            disabled={loading}
          >
            {loading ? "Sending..." : "Send"}
          </button>
        </div>

      </div>
    </div>
  );
}

export default App;