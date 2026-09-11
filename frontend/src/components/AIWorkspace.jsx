import { useRef, useState, Component } from "react";
import "./AIWorkspace.css";

// Simple Hindi/Urdu to Roman Hinglish transliteration
// This is a fallback for cases where backend transliteration didn't apply
const HINDI_HINGLISH_MAP = {
  // Devanagari vowels
  'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ii', 'उ': 'u', 'ऊ': 'uu',
  'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au',
  // Devanagari consonants
  'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
  'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
  'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
  'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
  'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
  'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v',
  'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h',
  // Matras
  'ा': 'aa', 'ि': 'i', 'ी': 'ii', 'ु': 'u', 'ू': 'uu',
  'ृ': 'ri', 'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au',
  '्': '',
  // Urdu
  'ا': 'a', 'ب': 'b', 'پ': 'p', 'ت': 't', 'ث': 's',
  'ج': 'j', 'چ': 'ch', 'ح': 'h', 'خ': 'kh', 'د': 'd',
  'ڈ': 'dh', 'ذ': 'z', 'ر': 'r', 'ز': 'z', 'ژ': 'zh',
  'س': 's', 'ش': 'sh', 'ص': 's', 'ض': 'z', 'ط': 't',
  'ظ': 'z', 'ع': 'a', 'غ': 'gh', 'ف': 'f', 'ق': 'q',
  'ک': 'k', 'گ': 'g', 'ل': 'l', 'م': 'm', 'ن': 'n',
  'و': 'o', 'ہ': 'h', 'ھ': 'h', 'ے': 'e', 'ی': 'y',
  'ء': '', 'ٔ': '', 'ٕ': '', 'ّ': '', 'ْ': '', 'ٰ': 'aa',
};

function transliterateToHinglish(text) {
  if (typeof text !== "string" || !text.trim()) return text;

  // If already ASCII-only English, leave unchanged
  const nonAscii = [...text].filter(ch => ch.charCodeAt(0) > 127).length;
  if (nonAscii / text.length < 0.3) {
    const lettersOnly = text.replace(/[^a-zA-Z\s]/g, "");
    if (lettersOnly.length > 0 && /^[a-zA-Z\s]+$/.test(lettersOnly))
      return text;
  }

  let result = "";
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (HINDI_HINGLISH_MAP[ch]) {
      result += HINDI_HINGLISH_MAP[ch];
    } else if (ch.match(/\s/)) {
      result += " ";
    } else if (/[.,!?;:'"()[\]{}-]/.test(ch)) {
      result += ch;
    }
    // Skip unmapped characters
  }
  return result.replace(/\s+/g, " ").trim();
}

// Error Boundary to catch rendering errors in the result display
class ResultErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Result rendering error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="ai-result-card" style={{ padding: "20px", textAlign: "center" }}>
          <div className="ai-result-card-heading">
            <h4>Display Error</h4>
          </div>
          <div style={{ color: "#fca5a5", padding: "15px", fontSize: "13px" }}>
            <p>Unable to display transcription results.</p>
            <p style={{ fontSize: "11px", opacity: 0.7, marginTop: "8px" }}>
              {this.state.error?.message || "Unknown rendering error"}
            </p>
            <button
              className="ai-upload-another"
              onClick={() => this.setState({ hasError: false, error: null })}
              style={{ marginTop: "15px" }}
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// Phrase-based notation layout for proper lyric-sargam alignment
// Each phrase = complete lyric phrase + corresponding sargam notation line

const WORDS_PER_PHRASE = 8;

function buildPhraseLayout(notes, lyricsData = null) {
  if (!notes || !notes.length) return { phrases: [], totalDuration: 0 };

  // If we have lyric segments with timing, use them to build phrases
  if (lyricsData && lyricsData.segments && lyricsData.segments.length > 0) {
    const segments = lyricsData.segments;
    const phrasesWithData = [];

    for (let i = 0; i < segments.length; i += WORDS_PER_PHRASE) {
      const phraseSegments = segments.slice(i, i + WORDS_PER_PHRASE);
      const phraseStart = phraseSegments[0].start ?? 0;
      const phraseEnd = phraseSegments[phraseSegments.length - 1].end ?? 0;

      // Find notes that fall within this phrase's time range
      const phraseNotes = notes.filter(n =>
        n.end > phraseStart && n.start < phraseEnd
      );

      // Build lyric phrase text (join words with spaces)
      const lyricPhrase = phraseSegments.map(s => s.word).join(" ");

      // Build notation phrase from the notes in this time range
      const sargamPhrase = phraseNotes.map(n => n.note).join(" ");

      // If no notes match this phrase's time range, fall back to using
      // the note symbols from the note's lyric array (legacy behavior)
      const fallbackSargam = phraseNotes.length === 0 && notes.length > 0
        ? notes.map(n => n.note).join(" ")
        : "";

      phrasesWithData.push({
        start: phraseStart,
        end: phraseEnd,
        duration: phraseEnd - phraseStart,
        lyricPhrase,
        sargamPhrase: sargamPhrase || fallbackSargam,
        words: phraseSegments.map(s => s.word),
        notes: phraseNotes,
      });
    }

    return { phrases: phrasesWithData };
  }

  // Fallback: if no lyric segments, group by note lyric arrays
  const groups = [];
  for (const n of notes) {
    const words = n.lyric || [];
    for (const word of words) {
      const last = groups[groups.length - 1];
      if (last && last.word === word) {
        last.symbols.push(n.note);
      } else {
        groups.push({ word, symbols: [n.note] });
      }
    }
    if (words.length === 0) {
      groups.push({ word: "", symbols: [n.note] });
    }
  }

  const lines = [];
  for (let i = 0; i < groups.length; i += WORDS_PER_PHRASE) {
    lines.push(groups.slice(i, i + WORDS_PER_PHRASE));
  }
  return { phrases: [], lines };
}

function buildNotationLines(notes) {
  // Legacy function for backward compatibility
  if (!notes || !notes.length) return [];

  const groups = [];
  for (const n of notes) {
    const words = n.lyric || [];
    for (const word of words) {
      const last = groups[groups.length - 1];
      if (last && last.word === word) {
        last.symbols.push(n.note);
      } else {
        groups.push({ word, symbols: [n.note] });
      }
    }
    if (words.length === 0) {
      groups.push({ word: "", symbols: [n.note] });
    }
  }

  const lines = [];
  for (let i = 0; i < groups.length; i += 6) {
    lines.push(groups.slice(i, i + 6));
  }
  return lines;
}

function AIWorkspace() {
  const [audioFile, setAudioFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [midiUrl, setMidiUrl] = useState(null);
  const [error, setError] = useState(null);
  const [lyrics, setLyrics] = useState("");
  const [autoLyrics, setAutoLyrics] = useState(false);

  const fileInputRef = useRef(null);

  // -----------------------------------------
  // Handle selected audio file
  // -----------------------------------------
  const handleFile = (file) => {
    if (!file) return;

    // Make sure the selected file is audio
    if (!file.type.startsWith("audio/")) {
      alert("Please select a valid audio file.");
      return;
    }

    setAudioFile(file);
    setResult(null);
    setMidiUrl(null);
    setError(null);
    setLyrics("");
  };

  // -----------------------------------------
  // Choose Audio button
  // -----------------------------------------
  const handleChooseAudio = () => {
    fileInputRef.current?.click();
  };

  // -----------------------------------------
  // File input
  // -----------------------------------------
  const handleFileChange = (event) => {
    const file = event.target.files[0];

    if (file) {
      handleFile(file);
    }
  };

  // -----------------------------------------
  // Drag over
  // -----------------------------------------
  const handleDragOver = (event) => {
    event.preventDefault();
    setIsDragging(true);
  };

  // -----------------------------------------
  // Drag leave
  // -----------------------------------------
  const handleDragLeave = () => {
    setIsDragging(false);
  };

  // -----------------------------------------
  // Drop audio file
  // -----------------------------------------
  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);

    const file = event.dataTransfer.files[0];

    if (file) {
      handleFile(file);
    }
  };

  // -----------------------------------------
  // Remove selected file
  // -----------------------------------------
  const handleRemoveFile = () => {
    setAudioFile(null);
    setResult(null);
    setMidiUrl(null);
    setError(null);
    setLyrics("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // -----------------------------------------
  // Format file size
  // -----------------------------------------
  const formatFileSize = (bytes) => {
    if (bytes < 1024) {
      return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }

    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  // -----------------------------------------
  // Transcribe audio
  // -----------------------------------------
  const handleTranscribe = async () => {
    if (!audioFile || isProcessing) return;

    setIsProcessing(true);
    setResult(null);
    setMidiUrl(null);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("audio", audioFile);

      if (autoLyrics) {
        formData.append("generateLyrics", "true");
      } else if (lyrics.trim()) {
        formData.append("lyrics", lyrics.trim());
      }

      const response = await fetch("/api/transcribe", {
        method: "POST",
        body: formData,
      });

      let data;
      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        data = await response.json();
      } else {
        const text = await response.text();
        throw new Error(text || `Server error: ${response.status}`);
      }

      if (!response.ok) {
        throw new Error(data?.detail || "Transcription failed.");
      }

      if (!data?.result) {
        throw new Error("Invalid response from server: missing result data");
      }

      setResult(data.result);
      setMidiUrl(data.midiUrl || null);
    } catch (err) {
      console.error("Transcription error:", err);
      setError(err.message || "Could not reach the Maestro backend.");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <section className="ai-workspace" id="ai-workspace">

      <div className="ai-workspace-container">

        {/* ================================
            SECTION HEADER
        ================================= */}

        <div className="ai-workspace-header">

          <span className="ai-workspace-eyebrow">
            MAESTRO AI WORKSPACE
          </span>

          <h2>
            Turn Your Music Into
            <span> Musical Data</span>
          </h2>

          <p>
            Upload an audio file and let Maestro analyze
            the music, identify instruments and generate
            a musical transcription.
          </p>

        </div>


        {/* ================================
            STEP 1 — UPLOAD
        ================================= */}

        {!audioFile && !isProcessing && !result && (

          <div
            className={`ai-upload-box ${
              isDragging ? "ai-upload-dragging" : ""
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >

            <div className="ai-upload-icon">
              ♪
            </div>

            <h3>
              Upload Your Audio
            </h3>

            <p>
              Drag & drop your music file here
            </p>

            <span className="ai-upload-or">
              or
            </span>

            <button
              className="ai-choose-button"
              onClick={handleChooseAudio}
            >
              Choose Audio
            </button>

            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              onChange={handleFileChange}
              hidden
            />

            <span className="ai-supported-formats">
              MP3 • WAV • FLAC • OGG
            </span>

          </div>

        )}


        {/* ================================
            STEP 2 — FILE SELECTED
        ================================= */}

        {audioFile && !isProcessing && !result && (

          <div className="ai-selected-wrapper">

            <div className="ai-selected-file">

              <div className="ai-file-icon">
                ♪
              </div>

              <div className="ai-file-details">

                <h3>
                  {audioFile.name}
                </h3>

                <p>
                  {audioFile.type || "Audio file"}
                  {" • "}
                  {formatFileSize(audioFile.size)}
                </p>

              </div>

              <button
                className="ai-remove-button"
                onClick={handleRemoveFile}
                title="Remove file"
              >
                ×
              </button>

            </div>


            <div className="ai-lyrics-box">

              <label className="ai-auto-lyrics-toggle">
                <input
                  type="checkbox"
                  checked={autoLyrics}
                  onChange={(e) => setAutoLyrics(e.target.checked)}
                  disabled={isProcessing}
                />
                <span>Auto-generate lyrics from vocals</span>
              </label>

              {!autoLyrics && (
                <textarea
                  className="ai-lyrics-input"
                  value={lyrics}
                  onChange={(e) => setLyrics(e.target.value)}
                  rows={2}
                  placeholder="Add lyrics (optional) — Maestro aligns words to your notes"
                />
              )}

              {autoLyrics && (
                <p className="ai-auto-lyrics-hint">
                  Maestro will listen to the vocals and write the lyrics automatically.
                </p>
              )}

            </div>


            <button
              className="ai-transcribe-button"
              onClick={handleTranscribe}
            >
              <span>✦</span>
              Transcribe Audio
            </button>

            {error && (
              <p className="ai-error-message">
                {error}
              </p>
            )}

          </div>

        )}


        {/* ================================
            STEP 3 — PROCESSING
        ================================= */}

        {isProcessing && (

          <div className="ai-processing-card">

            <div className="ai-processing-animation">

              <div className="ai-pulse-ring"></div>

              <div className="ai-processing-note">
                ♪
              </div>

            </div>

            <h3>
              Maestro is listening...
            </h3>

            <p>
              Analyzing instruments, notes and
              musical patterns
            </p>

            <div className="ai-processing-bar">

              <div className="ai-processing-progress"></div>

            </div>

            <span className="ai-processing-status">
              Processing audio...
            </span>

          </div>

        )}


        {/* ================================
            STEP 4 — TRANSCRIPTION RESULT
        ================================= */}

        {result && !isProcessing && (
          <div className="ai-result">

            {/* Result heading */}

            <div className="ai-result-header">

              <div>

                <span className="ai-result-label">
                  TRANSCRIPTION COMPLETE
                </span>

                <h3>
                  Transcription Result
                </h3>

                <p>
                  Generated from{" "}
                  <strong>
                    {audioFile?.name}
                  </strong>
                </p>

              </div>

              <div className="ai-result-check">
                ✓
              </div>

            </div>


            {/* Music information */}

            <div className="ai-music-info">

              <div className="ai-info-card">
                <span>Duration</span>
                <strong>{result.duration || "—"}</strong>
              </div>

              <div className="ai-info-card">
                <span>Tempo</span>
                <strong>{result.tempo ? `${result.tempo} BPM` : "—"}</strong>
              </div>

              <div className="ai-info-card">
                <span>Key</span>
                <strong>{result.key || "—"}</strong>
              </div>

              <div className="ai-info-card">
                <span>Time Signature</span>
                <strong>{result.timeSignature || "—"}</strong>
              </div>

            </div>


            {/* Detected instruments */}

            <div className="ai-result-card">

              <div className="ai-result-card-heading">

                <h4>
                  Detected Instruments
                </h4>

                <span>
                  {result.instruments?.length || 0}
                </span>

              </div>

              <div className="ai-instrument-list">

                {(result.instruments || []).map(
                  (instrument, index) => (

                    <div
                      className="ai-instrument-tag"
                      key={index}
                    >
                      <span>♪</span>
                      {instrument}
                    </div>

                  )
                )}

              </div>

            </div>

{/* Note transcription */}

            <ResultErrorBoundary>
              <div className="ai-result-card">

                <div className="ai-result-card-heading">

                  <h4>
                    Lyrics & Notation
                  </h4>

                  <span>
                    {result.notes?.length || 0} notes
                  </span>

                </div>


                <div className="ai-notation-output">

                  {(result.notes && result.notes.length > 0) ? (() => {
                    const layout = buildPhraseLayout(result.notes, result.lyrics);
                    if (layout.phrases && layout.phrases.length > 0) {
                      return layout.phrases.map((phrase, pi) => (
                        <div className="ai-phrase-block" key={pi}>
                          <div className="ai-lyric-phrase-line">
                            {transliterateToHinglish(phrase.lyricPhrase)}
                          </div>
                          <div className="ai-sargam-phrase-line">
                            {phrase.sargamPhrase || "—"}
                          </div>
                        </div>
                      ));
                    }
                    // Fallback to legacy line-based rendering
                    return buildNotationLines(result.notes).map(
                      (line, li) => (
                        <div className="ai-notation-line" key={li}>
                          {line.map((group, gi) => (
                            <div className="ai-notation-group" key={gi}>
                              <div className="ai-notation-vertical">
                                <span className="ai-notation-word">
                                  {transliterateToHinglish(group.word || "·")}
                                </span>
                                <span className="ai-notation-symbols">
                                  {group.symbols?.join(" ") || ""}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )
                    );
                  })() : (
                    <div className="ai-notation-empty">No notes detected</div>
                  )}

                </div>

              </div>
            </ResultErrorBoundary>


            {/* Result actions */}

            <div className="ai-result-actions">

              <button
                className="ai-upload-another"
                onClick={handleRemoveFile}
              >
                Upload Another
              </button>

              <button
                className="ai-download-button"
                disabled={!midiUrl}
                onClick={() => {
                  if (midiUrl) window.open(midiUrl, "_blank");
                }}
              >
                ↓ Download MIDI
              </button>

            </div>

          </div>

        )}

      </div>

    </section>
  );
}

export default AIWorkspace;