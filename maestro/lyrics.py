"""Lyric text processing and lyric-to-note alignment.

LyricProcessor: tokenizes text into words, splits syllables (vowel-group heuristic).
LyricAligner: aligns lyrics to notes using temporal overlap with primary ownership model.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .config import AppConfig
from .errors import ErrorCode, MaestroError
from .models import DetectedNote, LyricUnit

logger = logging.getLogger("maestro.lyrics")

_VOWEL = "aeiouyAEIOUY"

# Default timing tolerance for aligning Whisper timestamps to note boundaries (seconds)
DEFAULT_TIME_TOLERANCE = 0.15
# Ownership threshold: minimum overlap score for a note to claim a lyric as primary
DEFAULT_OWNERSHIP_THRESHOLD = 0.35
# Candidate tolerance: used to find nearby notes for a word (smaller than ownership)
DEFAULT_CANDIDATE_TOLERANCE = 0.05


def split_syllables(word: str) -> list[str]:
    """Split word into syllables with a consonant+vowel heuristic."""
    word = word.strip()
    if not word:
        return []
    if not any(c in _VOWEL for c in word):
        return [word]

    groups: list[str] = []
    cur = ""
    prev_is_vowel = False
    for ch in word:
        if not (ch.isalpha() or ch in "'-"):
            continue
        is_vowel = ch in _VOWEL
        if is_vowel:
            cur += ch
        else:
            if cur and prev_is_vowel:
                groups.append(cur)
                cur = ""
            cur += ch
        prev_is_vowel = is_vowel
    if cur:
        groups.append(cur)
    return groups


class LyricProcessor:
    def process(self, text: str) -> list[LyricUnit]:
        text = (text or "").strip()
        if not text:
            raise MaestroError(ErrorCode.LYRICS_ALIGNMENT_FAILED, "lyrics text is empty")
        words = text.split()
        units: list[LyricUnit] = []
        for i, word in enumerate(words):
            cleaned = re.sub(r"[^\w'']", "", word.strip())
            if not cleaned:
                continue
            units.append(
                LyricUnit(
                    word=cleaned,
                    index=i,
                    syllables=split_syllables(cleaned),
                )
            )
        if not units:
            raise MaestroError(ErrorCode.LYRICS_ALIGNMENT_FAILED, "no usable lyric words found")
        return units

    def process_with_whisper_timestamps(self, text: str, whisper_words: list) -> list[LyricUnit]:
        """Process lyrics text and attach Whisper word timestamps to each unit.
        
        Args:
            text: Full lyrics text (for splitting into words)
            whisper_words: List of WordTimestamp objects from Whisper
        """
        text = (text or "").strip()
        if not text:
            raise MaestroError(ErrorCode.LYRICS_ALIGNMENT_FAILED, "lyrics text is empty")
        words = text.split()
        units: list[LyricUnit] = []
        
        # Match text words to Whisper words by index (assuming same order)
        for i, word in enumerate(words):
            cleaned = re.sub(r"[^\w'']", "", word.strip())
            if not cleaned:
                continue
            unit = LyricUnit(
                word=cleaned,
                index=i,
                syllables=split_syllables(cleaned),
            )
            # Attach Whisper timestamps if available for this word index
            if i < len(whisper_words):
                ww = whisper_words[i]
                unit.whisper_start = ww.start
                unit.whisper_end = ww.end
                unit.whisper_confidence = ww.confidence
            units.append(unit)
        if not units:
            raise MaestroError(ErrorCode.LYRICS_ALIGNMENT_FAILED, "no usable lyric words found")
        return units


class LyricAligner:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        # Tolerance for finding candidate notes (small - just boundary slop)
        self.candidate_tolerance = getattr(config, 'lyric_candidate_tolerance', DEFAULT_CANDIDATE_TOLERANCE)
        # Threshold for a note to claim a word as its primary lyric
        self.ownership_threshold = getattr(config, 'lyric_ownership_threshold', DEFAULT_OWNERSHIP_THRESHOLD)
        # Legacy tolerance for backward compatibility
        self.time_tolerance = getattr(config, 'lyric_alignment_tolerance', DEFAULT_TIME_TOLERANCE)

    def align(self, units: list[LyricUnit], notes: list[DetectedNote]) -> list[LyricUnit]:
        """Align lyric words to detected vocal notes using temporal overlap with primary ownership.
        
        If units have Whisper timestamps (whisper_start/whisper_end), use those.
        Otherwise fall back to time-proportional allocation.
        """
        if not notes:
            raise MaestroError(
                ErrorCode.LYRICS_ALIGNMENT_FAILED,
                "cannot align lyrics: no musical notes detected",
            )
        if not units:
            raise MaestroError(ErrorCode.LYRICS_ALIGNMENT_FAILED, "no lyric units to align")

        # Check if we have Whisper timestamps
        has_whisper = any(u.whisper_start is not None and u.whisper_end is not None for u in units)
        
        if has_whisper:
            return self._align_with_whisper(units, notes)
        else:
            return self._align_time_proportional(units, notes)

    def _align_with_whisper(self, units: list[LyricUnit], notes: list[DetectedNote]) -> list[LyricUnit]:
        """Align using Whisper word timestamps with primary ownership model.
        
        Algorithm:
        1. For each word, find candidate notes that overlap its time range (with small tolerance for search)
        2. Calculate ACTUAL overlap using real word boundaries (no tolerance)
        3. For each note, determine its primary lyric owner based on strongest ACTUAL overlap
        4. Build word-to-notes mapping: a word gets ONLY notes where it is the PRIMARY owner
        5. Handle melisma: one word can own multiple consecutive notes (primary ownership)
        6. Preserve all words and all notes (unmatched get empty lists/null)
        """
        if not units or not notes:
            return units

        # Step 1: For each word, find candidate notes with their ACTUAL overlap scores
        word_candidates: list[list[dict]] = []  # word_idx -> list of candidate notes
        
        for unit in units:
            word_start = unit.whisper_start
            word_end = unit.whisper_end
            
            if word_start is None or word_end is None:
                word_candidates.append([])
                continue
            
            # Use small candidate tolerance ONLY to find nearby candidate notes
            tol = self.candidate_tolerance
            word_start_search = word_start - tol
            word_end_search = word_end + tol
            
            candidates: list[dict] = []
            for note_idx, note in enumerate(notes):
                # Check if note is a candidate (using search range with tolerance)
                if note.end <= word_start_search or note.start >= word_end_search:
                    continue
                
                # Calculate ACTUAL overlap using REAL word boundaries (NO tolerance)
                overlap_start = max(word_start, note.start)
                overlap_end = min(word_end, note.end)
                overlap_duration = max(0.0, overlap_end - overlap_start)
                
                if overlap_duration > 0:
                    word_duration = word_end - word_start
                    note_duration = note.duration
                    
                    word_overlap_ratio = overlap_duration / word_duration if word_duration > 0 else 0
                    note_overlap_ratio = overlap_duration / note_duration if note_duration > 0 else 0
                    
                    # Primary score: how much of the note is covered by this word
                    # This determines note ownership
                    ownership_score = note_overlap_ratio
                    
                    # Secondary score: how much of the word is covered by this note
                    # This determines melisma (word spans multiple notes)
                    word_coverage_score = word_overlap_ratio
                    
                    # Combined score for ranking candidates
                    overlap_score = 0.6 * ownership_score + 0.4 * word_coverage_score
                    
                    candidates.append({
                        'note_index': note_idx,
                        'note_start': note.start,
                        'note_end': note.end,
                        'note_duration': note_duration,
                        'overlap_duration': overlap_duration,
                        'word_overlap_ratio': word_overlap_ratio,
                        'note_overlap_ratio': note_overlap_ratio,
                        'ownership_score': ownership_score,
                        'word_coverage_score': word_coverage_score,
                        'overlap_score': overlap_score,
                        'midi_note': note.midi_note,
                        'frequency': note.frequency,
                    })
            
            # Sort by overlap score descending
            candidates.sort(key=lambda x: x['overlap_score'], reverse=True)
            word_candidates.append(candidates)

        # Step 2: Determine primary lyric owner for each note
        # A note's primary owner is the word with the highest ownership_score for that note
        # Only assign if above ownership_threshold
        note_primary_owner: dict[int, int] = {}  # note_idx -> word_idx
        note_ownership_scores: dict[int, float] = {}  # note_idx -> best ownership_score
        
        for word_idx, candidates in enumerate(word_candidates):
            for cand in candidates:
                note_idx = cand['note_index']
                ownership = cand['ownership_score']
                
                # Only consider as owner if above threshold
                if ownership >= self.ownership_threshold:
                    if note_idx not in note_ownership_scores or ownership > note_ownership_scores[note_idx]:
                        note_ownership_scores[note_idx] = ownership
                        note_primary_owner[note_idx] = word_idx

        # Step 3: Build word-to-notes mapping
        # Each word gets ONLY notes where it is the PRIMARY owner
        # This prevents over-attachment (one note -> multiple words)
        # Melisma is naturally handled: a word primary-owning multiple consecutive notes
        aligned_units: list[LyricUnit] = []
        
        for word_idx, unit in enumerate(units):
            word_start = unit.whisper_start
            word_end = unit.whisper_end
            word_conf = unit.whisper_confidence or 1.0
            
            if word_start is None or word_end is None:
                unit.alignment_method = "whisper-missing"
                unit.confidence = 0.0
                unit.notes = []
                unit.start = 0.0
                unit.end = 0.0
                aligned_units.append(unit)
                continue
            
            # Find notes where this word is the primary owner
            owned_note_indices = [
                note_idx for note_idx, owner_idx in note_primary_owner.items()
                if owner_idx == word_idx
            ]
            
            # Sort by note start time (chronological)
            owned_note_indices.sort(key=lambda idx: notes[idx].start)
            
            if owned_note_indices:
                first_note = notes[owned_note_indices[0]]
                last_note = notes[owned_note_indices[-1]]
                
                unit.start = round(first_note.start, 6)
                unit.end = round(last_note.end, 6)
                unit.notes = owned_note_indices
                
                # Confidence based on average ownership score of owned notes
                owned_scores = [note_ownership_scores.get(idx, 0) for idx in owned_note_indices]
                if owned_scores:
                    unit.confidence = round(sum(owned_scores) / len(owned_scores), 4)
                else:
                    unit.confidence = 0.0
                
                unit.alignment_method = "whisper-temporal"
                
                # Store detailed note info for output (only primary-owned notes)
                unit._aligned_notes = [c for c in candidates if c['note_index'] in owned_note_indices]  # type: ignore
            else:
                # No primary-owned notes - keep word but mark as unmatched
                unit.start = round(word_start, 6)
                unit.end = round(word_end, 6)
                unit.notes = []
                unit.confidence = 0.0
                unit.alignment_method = "whisper-unmatched"
                unit._aligned_notes = []  # type: ignore
            
            aligned_units.append(unit)
        
        return aligned_units

    def _align_time_proportional(self, units: list[LyricUnit], notes: list[DetectedNote]) -> list[LyricUnit]:
        """Fallback: original time-proportional alignment."""
        span_start = notes[0].start
        span_end = notes[-1].end
        span = max(1e-6, span_end - span_start)

        weights = [max(1, len(u.syllables)) for u in units]
        total = sum(weights)

        cursor = 0.0
        slots: list[tuple[float, float]] = []
        for w in weights:
            start = span_start + cursor * span / total
            cursor += w
            end = span_start + cursor * span / total
            slots.append((start, end))

        out: list[LyricUnit] = []
        for unit, (slot_start, slot_end) in zip(units, slots):
            attached = [
                (i, n) for i, n in enumerate(notes) if _overlaps(n, slot_start, slot_end)
            ]
            if not attached:
                idx = min(range(len(notes)), key=lambda i: _distance(notes[i], slot_start))
                attached = [(idx, notes[idx])]
            attached.sort(key=lambda it: it[1].start)
            note_idx = [i for i, _ in attached]
            first = attached[0][1]
            last = attached[-1][1]

            seg_start = first.start
            seg_end = last.end

            covered = sum(max(0.0, min(seg_end, n.end) - max(seg_start, n.start)) for _, n in attached)
            slot_len = max(1e-6, slot_end - slot_start)
            timing_conf = min(1.0, covered / slot_len)
            pitch_conf = float(min(max(n.confidence for _, n in attached), 1.0))
            confidence = round(0.6 * timing_conf + 0.4 * pitch_conf, 4)

            unit.start = round(seg_start, 6)
            unit.end = round(seg_end, 6)
            unit.notes = note_idx
            unit.confidence = confidence
            unit.alignment_method = "time-proportional"
            out.append(unit)

        return out


def _overlaps(note: DetectedNote, start: float, end: float) -> bool:
    return note.end > start and note.start < end


def _distance(note: DetectedNote, t: float) -> float:
    if note.start <= t <= note.end:
        return 0.0
    return min(abs(note.start - t), abs(note.end - t))
