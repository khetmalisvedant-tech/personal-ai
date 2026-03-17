import { useState, useEffect, useRef } from "react";

// ── Language detection ────────────────────────────────────────────────────────
const MARATHI_KEYWORDS = new Set([
  "आहे","आणि","काय","कसे","मला","तुम्ही","आपण",
  "सांगा","करा","हे","ते","नाही","होय","मराठी",
  "त्याचा","त्याची","आम्ही","तुमचा","कोण","कुठे",
]);
const HINDI_KEYWORDS = new Set([
  "है","और","क्या","कैसे","मुझे","आप","हम",
  "बताओ","करो","यह","वह","नहीं","हाँ","हिंदी",
  "उसका","उसकी","तुम्हारा","कौन","कहाँ","मैं",
]);

function detectLanguage(text) {
  let hasDevanagari = false;
  for (const ch of text) {
    const c = ch.codePointAt(0);
    if (c >= 0x0900 && c <= 0x097f) { hasDevanagari = true; break; }
  }
  if (!hasDevanagari) return "english";
  const words = new Set(text.split(/\s+/));
  for (const w of words) if (MARATHI_KEYWORDS.has(w)) return "marathi";
  for (const w of words) if (HINDI_KEYWORDS.has(w))   return "hindi";
  return "hindi";
}

const PLACEHOLDER = {
  english: "Type your question here, or click 🎤 to speak...",
  hindi:   "यहाँ अपना सवाल लिखें, या 🎤 बोलने के लिए क्लिक करें...",
  marathi: "येथे तुमचा प्रश्न लिहा, किंवा 🎤 बोलण्यासाठी क्लिक करा...",
};
const LANG_ATTR  = { english: "en", hindi: "hi", marathi: "mr" };
const LANG_LABEL = { english: "EN", hindi: "HI", marathi: "MR" };

// ── Skeleton shimmer block ────────────────────────────────────────────────────
function Skeleton({ width = "100%", height = "16px", style = {} }) {
  return (
    <div style={{
      width, height,
      borderRadius: "6px",
      background: "rgba(255,255,255,0.08)",
      backgroundImage: "linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.07) 50%, rgba(255,255,255,0) 100%)",
      backgroundSize: "200% 100%",
      animation: "shimmer 1.4s infinite",
      ...style,
    }} />
  );
}

// ── Initial response state ────────────────────────────────────────────────────
const EMPTY_RESPONSE = {
  explanation: "",
  summary:     "",
  quiz:        [],
  audioUrl:    null,
  audioError:  "",
  error:       "",
  loading:     false,
};

// ── Component ─────────────────────────────────────────────────────────────────
export default function App() {
  const [question,  setQuestion]  = useState("");
  const [inputLang, setInputLang] = useState("english");
  const [listening, setListening] = useState(false);

  // ── ALL response data in one object so React batches into a single render ──
  const [res, setRes] = useState(EMPTY_RESPONSE);

  const audioRef = useRef(null);

  // Play audio only when audioUrl actually changes to a non-null value
  useEffect(() => {
    if (res.audioUrl && audioRef.current) {
      audioRef.current.src = res.audioUrl;
      audioRef.current.play().catch(() => {});
    }
  }, [res.audioUrl]);

  const handleQuestionChange = (e) => {
    const val = e.target.value;
    setQuestion(val);
    setInputLang(val.trim() ? detectLanguage(val) : "english");
  };

  const sendQuestion = async (q) => {
    if (!q?.trim()) return;

    // Single setState call → single re-render: clears old data + shows skeleton
    setRes({ ...EMPTY_RESPONSE, loading: true });

    try {
      const response = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });

      if (!response.ok) {
        // Single setState → single re-render
        setRes({ ...EMPTY_RESPONSE, error: `Server error: ${response.status}` });
        return;
      }

      const data = await response.json();

      if (data.error) {
        setRes({ ...EMPTY_RESPONSE, error: data.error });
        return;
      }

      // ── ONE setState here = ONE render with the complete response ──────────
      setRes({
        loading:    false,
        error:      "",
        explanation: data.explanation  || "",
        summary:     data.summary      || "",
        quiz:        Array.isArray(data.quiz) ? data.quiz : [],
        audioUrl:    data.audio        || null,
        audioError:  data.audio_error  || "",
      });

    } catch (err) {
      setRes({ ...EMPTY_RESPONSE, error: "Could not connect to server. Is it running?" });
    }
  };

  const startVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert("Speech recognition not supported."); return; }

    const rec = new SR();
    rec.lang = inputLang === "english" ? "en-IN" : "hi-IN";
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    rec.onstart  = () => setListening(true);
    rec.onend    = () => setListening(false);
    rec.onerror  = (e) => {
      setListening(false);
      setRes(prev => ({ ...prev, error: `Voice error: ${e.error}` }));
    };
    rec.onresult = (e) => {
      const spoken = e.results[0][0].transcript;
      setQuestion(spoken);
      setInputLang(detectLanguage(spoken));
      sendQuestion(spoken);
    };
    rec.start();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendQuestion(question); }
  };

  const { loading, error, explanation, summary, quiz, audioUrl, audioError } = res;

  return (
    <>
      <style>{`
        @keyframes shimmer {
          0%   { background-position: -200% 0; }
          100% { background-position:  200% 0; }
        }
      `}</style>

      <div style={styles.page}>
        <div style={styles.card}>

          {/* Header */}
          <div style={styles.header}>
            <span style={styles.icon}>🎓</span>
            <h1 style={styles.title}>Voice AI Tutor</h1>
            <p style={styles.subtitle}>Ask anything. Learn everything.</p>
          </div>

          {/* Input */}
          <div style={styles.inputRow}>
            <div style={styles.textareaWrapper}>
              <span style={styles.langBadge}>{LANG_LABEL[inputLang]}</span>
              <textarea
                lang={LANG_ATTR[inputLang]}
                style={{
                  ...styles.textarea,
                  fontSize: inputLang === "english" ? "1rem" : "1.05rem",
                }}
                placeholder={PLACEHOLDER[inputLang]}
                value={question}
                onChange={handleQuestionChange}
                onKeyDown={handleKeyDown}
                rows={2}
              />
            </div>

            <div style={styles.btnGroup}>
              <button
                style={{ ...styles.btn, ...styles.btnVoice }}
                onClick={startVoice}
                disabled={loading}
              >
                {listening ? "🔴 Listening..." : "🎤 Speak"}
              </button>
              <button
                style={{ ...styles.btn, ...styles.btnAsk }}
                onClick={() => sendQuestion(question)}
                disabled={loading || !question.trim()}
              >
                {loading ? "⏳ Thinking..." : "Ask →"}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && <div style={styles.error}>⚠️ {error}</div>}

          {/* ── Skeleton: shown only while loading ── */}
          {loading && (
            <>
              <div style={styles.section}>
                <Skeleton height="13px" width="60px" style={{ marginBottom: "14px" }} />
                <Skeleton height="14px" style={{ marginBottom: "10px" }} />
                <Skeleton height="14px" width="90%" style={{ marginBottom: "10px" }} />
                <Skeleton height="14px" width="75%" />
              </div>
              <div style={styles.section}>
                <Skeleton height="13px" width="80px" style={{ marginBottom: "14px" }} />
                {[1, 2, 3].map(i => (
                  <Skeleton key={i} height="14px" width={`${85 - i * 5}%`} style={{ marginBottom: "10px" }} />
                ))}
              </div>
            </>
          )}

          {/* ── Full response: rendered ALL AT ONCE when loading is false ── */}
          {!loading && explanation && (
            <>
              {/* Explanation */}
              <div style={styles.section}>
                <h2 style={styles.sectionTitle}>📘 Explanation</h2>
                <p style={styles.explanationText}>{explanation}</p>
              </div>

              {/* Summary */}
              {summary && (
                <div style={{ ...styles.section, ...styles.summaryBox }}>
                  <h2 style={styles.sectionTitle}>💡 Summary</h2>
                  <p style={styles.summaryText}>{summary}</p>
                </div>
              )}

              {/* Audio */}
              {audioUrl && (
                <div style={styles.section}>
                  <h2 style={styles.sectionTitle}>🔊 Listen</h2>
                  <audio ref={audioRef} controls style={styles.audio} src={audioUrl} />
                </div>
              )}
              {audioError && <div style={styles.audioError}>🔇 {audioError}</div>}

              {/* Quiz */}
              {quiz.length > 0 && (
                <div style={styles.section}>
                  <h2 style={styles.sectionTitle}>🧠 Practice Questions</h2>
                  <ol style={styles.quizList}>
                    {quiz.map((q, i) => (
                      <li key={i} style={styles.quizItem}>{q}</li>
                    ))}
                  </ol>
                </div>
              )}
            </>
          )}

        </div>
      </div>
    </>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
const styles = {
  page: {
    height: "100vh",
    width: "98vw",
    background: "linear-gradient(135deg, #0f0c29, #302b63, #24243e)",
    display: "flex", alignItems: "center", justifyContent: "center",
    padding: "40px 16px",
    fontFamily: "'Segoe UI', sans-serif",
  },
  card: {
    background: "rgba(255,255,255,0.05)",
    backdropFilter: "blur(16px)",
    borderRadius: "20px",
    border: "1px solid rgba(255,255,255,0.12)",
    padding: "36px",
    width: "100%", maxWidth: "720px",
    color: "#f0f0f0",
    boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
  },
  header: { textAlign: "center", marginBottom: "32px" },
  icon:   { fontSize: "48px" },
  title: {
    fontSize: "2rem", fontWeight: 700, margin: "8px 0 4px",
    background: "linear-gradient(90deg, #a78bfa, #60a5fa)",
    WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
  },
  subtitle: { color: "#9ca3af", fontSize: "0.95rem", margin: 0 },
  inputRow: { display: "flex", flexDirection: "column", gap: "12px" },
  textareaWrapper: { position: "relative", width: "100%" },
  langBadge: {
    position: "absolute", top: "8px", right: "10px",
    background: "rgba(167,139,250,0.25)", color: "#c4b5fd",
    fontSize: "0.7rem", fontWeight: 700, letterSpacing: "0.1em",
    padding: "2px 8px", borderRadius: "20px",
    pointerEvents: "none", zIndex: 1, userSelect: "none",
  },
  textarea: {
    width: "100%", padding: "12px 48px 12px 16px",
    borderRadius: "12px", border: "1px solid rgba(255,255,255,0.15)",
    background: "rgba(255,255,255,0.08)", color: "#fff",
    resize: "vertical", outline: "none", boxSizing: "border-box",
    lineHeight: 1.6,
  },
  btnGroup: { display: "flex", gap: "12px" },
  btn: {
    flex: 1, padding: "12px", borderRadius: "10px", border: "none",
    fontWeight: 600, fontSize: "0.95rem", cursor: "pointer",
  },
  btnVoice: { background: "#7c3aed", color: "#fff" },
  btnAsk:   { background: "#2563eb", color: "#fff" },
  error: {
    marginTop: "16px", padding: "12px 16px",
    background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.4)",
    borderRadius: "10px", color: "#fca5a5", fontSize: "0.9rem",
  },
  audioError: { marginTop: "8px", color: "#f59e0b", fontSize: "0.85rem", padding: "8px 12px" },
  section: {
    marginTop: "24px", padding: "20px",
    background: "rgba(255,255,255,0.05)",
    borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)",
  },
  summaryBox: {
    background: "rgba(96,165,250,0.08)",
    border: "1px solid rgba(96,165,250,0.2)",
  },
  sectionTitle: {
    fontSize: "1rem", fontWeight: 700, margin: "0 0 12px",
    color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em",
  },
  explanationText: { lineHeight: 1.75, fontSize: "1rem", margin: 0 },
  summaryText: { lineHeight: 1.65, fontSize: "0.95rem", color: "#bfdbfe", margin: 0 },
  audio:     { width: "100%", marginTop: "4px" },
  quizList:  { paddingLeft: "20px", margin: 0 },
  quizItem:  { marginBottom: "10px", lineHeight: 1.6, fontSize: "0.95rem", color: "#e2e8f0" },
};
