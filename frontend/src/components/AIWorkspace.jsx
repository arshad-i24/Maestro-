import { useRef, useState } from "react";
import "./AIWorkspace.css";

const WORDS_PER_LINE = 4;

function buildNotationLines(notes) {
  if (!notes || !notes.length) return [];

  const groups = [];
  for (const n of notes) {
    const word = n.lyric || "";
    const last = groups[groups.length - 1];
    if (last && last.word === word) {
      last.symbols.push(n.note);
    } else {
      groups.push({ word, symbols: [n.note] });
    }
  }

  const lines = [];
  for (let i = 0; i < groups.length; i += WORDS_PER_LINE) {
    lines.push(groups.slice(i, i + WORDS_PER_LINE));
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

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Transcription failed.");
      }

      setResult(data.result);
      setMidiUrl(data.midiUrl || null);
    } catch (err) {
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
                <strong>{result.duration}</strong>
              </div>

              <div className="ai-info-card">
                <span>Tempo</span>
                <strong>{result.tempo} BPM</strong>
              </div>

              <div className="ai-info-card">
                <span>Key</span>
                <strong>{result.key}</strong>
              </div>

              <div className="ai-info-card">
                <span>Time Signature</span>
                <strong>{result.timeSignature}</strong>
              </div>

            </div>


            {/* Detected instruments */}

            <div className="ai-result-card">

              <div className="ai-result-card-heading">

                <h4>
                  Detected Instruments
                </h4>

                <span>
                  {result.instruments.length}
                </span>

              </div>

              <div className="ai-instrument-list">

                {result.instruments.map(
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

            <div className="ai-result-card">

              <div className="ai-result-card-heading">

                <h4>
                  Lyrics & Notation
                </h4>

                <span>
                  {result.notes.length} notes
                </span>

              </div>


              <div className="ai-notation-output">

                {buildNotationLines(result.notes).map(
                  (line, li) => (

                    <div
                      className="ai-notation-line"
                      key={li}
                    >

                      {line.map((group, gi) => (

                        <div
                          className="ai-notation-group"
                          key={gi}
                        >

                          <span className="ai-notation-word">
                            {group.word || "·"}
                          </span>

                          <span className="ai-notation-symbols">
                            {group.symbols.join(" ")}
                          </span>

                        </div>

                      ))}

                    </div>

                  )
                )}

              </div>

            </div>


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