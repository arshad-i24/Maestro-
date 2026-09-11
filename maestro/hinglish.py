"""Hindi/Urdu to Roman Hinglish transliteration.

Provides presentation-layer transliteration without modifying the
core music notation or lyric-note alignment pipeline.

Maps Devanagari and selected Urdu/Arabic script characters to
readable Roman Hindi equivalents for display purposes.
"""


# Devanagari (Hindi) to Roman Hinglish mapping
# Based on common Hindi song lyrics and natural transliteration preferences
_DEVANAGARI_TO_HINGLISH = {
    # Independent vowels
    '\u0905': 'a',   # अ
    '\u0906': 'aa',  # आ
    '\u0907': 'i',   # इ
    '\u0908': 'ii',  # ई
    '\u0909': 'u',   # उ
    '\u090a': 'uu',  # ऊ
    '\u090b': 'ri',  # ऋ
    '\u090c': 'rii', # ॠ
    '\u090d': 'lri', # ऌ
    '\u090e': 'lrii',# ॡ
    '\u090f': 'e',   # ए
    '\u0910': 'ai',  # ऐ
    '\u0911': 'o',   # ओ
    '\u0912': 'au',  # औ
    '\u0913': '',    # (unused)
    '\u0914': '',    # (unused)

    # Vowel signs (matras) - these modify the inherent 'a' of consonants
    '\u093e': 'aa',  # ा  (aa)
    '\u093f': 'i',   # ि  (i)
    '\u0940': 'ii',  # ी  (ii)
    '\u0941': 'u',   # ु  (u)
    '\u0942': 'uu',  # ू  (uu)
    '\u0943': 'ri',  # ृ  (ri)
    '\u0944': 'rii', # ॄ  (rii)
    '\u0945': '',    # ॅ (candra e)
    '\u0946': '',    # ॆ (candra o)
    '\u0947': 'e',   # े  (e)
    '\u0948': 'ai',  # ै  (ai)
    '\u0949': '',    # ॉ (candra o)
    '\u094a': '',    # ॊ (candra o)
    '\u094b': 'o',   # ो  (o)
    '\u094c': 'au',  # ौ  (au)

    # Virama (halant) - removes inherent vowel
    '\u094d': '',    # ्  (halant)

    # Consonants (with inherent 'a' vowel) - correct Unicode codepoints
    '\u0915': 'k',   # क
    '\u0916': 'kh',  # ख
    '\u0917': 'g',   # ग
    '\u0918': 'gh',  # घ
    '\u0919': 'ng',  # ङ
    '\u091a': 'ch',  # च
    '\u091b': 'chh', # छ
    '\u091c': 'j',   # ज
    '\u091d': 'jh',  # झ
    '\u091e': 'ny',  # ञ

    # Retroflex consonants
    '\u091f': 't',   # ट
    '\u0920': 'th',  # ठ
    '\u0921': 'd',   # ड
    '\u0922': 'dh',  # ढ
    '\u0923': 'n',   # ण

    # Dental consonants
    '\u0924': 't',   # त
    '\u0925': 'th',  # थ
    '\u0926': 'd',   # द
    '\u0927': 'dh',  # ध
    '\u0928': 'n',   # न

    # Labial consonants
    '\u092a': 'p',   # प
    '\u092b': 'ph',  # फ
    '\u092c': 'b',   # ब
    '\u092d': 'bh',  # भ
    '\u092e': 'm',   # म

# Semivowels
    '\u092f': 'y',   # य
    '\u0930': 'r',   # र
    '\u0931': 'l',   # ळ (Marathi)
    '\u0932': 'l',   # ल
    '\u0933': 'll',  # ऴ (Marathi/Tamil)
    '\u0934': 'v',   # व (deprecated - use U+0935)
    '\u0935': 'v',   # व
    '\u0936': 'sh',  # श
    '\u0937': 'sh',  # ष
    '\u0938': 's',   # स
    '\u0939': 'h',   # ह

    # Devanagari digits
    '\u0966': '0',
    '\u0967': '1',
    '\u0968': '2',
    '\u0969': '3',
    '\u096a': '4',
    '\u096b': '5',
    '\u096c': '6',
    '\u096d': '7',
    '\u096e': '8',
    '\u096f': '9',

    # Punctuation
    '\u0964': '.',   # । (purna viram)
    '\u0965': '..',  # ॥ (deergh viram)

    # Nukta (for foreign sounds)
    '\u093c': '',    # ़

    # Devanagari digits (keep as-is or map)
    '\u0966': '0',
    '\u0967': '1',
    '\u0968': '2',
    '\u0969': '3',
    '\u096a': '4',
    '\u096b': '5',
    '\u096c': '6',
    '\u096d': '7',
    '\u096e': '8',
    '\u096f': '9',

    # Punctuation
    '\u0964': '.',   # । (purna viram)
    '\u0965': '..',  # ॥ (deergh viram)

    # Nukta (for foreign sounds)
    '\u093c': '',    # ़

    # Common conjuncts/ligatures (approximate)
    '\u0915\u094d\u0937': 'ksh',  # क्ष
    '\u091c\u094d\u091e': 'gya',  # ज्ञ
    '\u0924\u094d\u0930': 'tr',   # त्र
    '\u0936\u094d\u0930': 'shr',  # श्र
}


# Urdu/Arabic-derived characters that may appear
# These are Arabic/Persic characters used in Urdu
_URDU_TO_HINGLISH = {
    # Basic Arabic letters used in Urdu (isolated forms)
    '\u0627': 'a',   # ا (alif)
    '\u0628': 'b',   # ب (be)
    '\u067e': 'p',   # پ (pe)
    '\u062a': 't',   # ت (te)
    '\u062b': 's',   # ث (se)
    '\u062c': 'j',   # ج (jeem)
    '\u0686': 'ch',  # چ (che)
    '\u062d': 'h',   # ح (baari he)
    '\u062e': 'kh',  # خ (khe)
    '\u062f': 'd',   # د (daal)
    '\u0688': 'dh',  # ڈ (ddal)
    '\u0630': 'z',   # ذ (zaal)
    '\u0631': 'r',   # ر (re)
    '\u0632': 'z',   # ز (ze)
    '\u0698': 'zh',  # ژ (zhe)
    '\u0633': 's',   # س (seen)
    '\u0634': 'sh',  # ش (sheen)
    '\u0635': 's',   # ص (swad)
    '\u0636': 'z',   # ض (zwad)
    '\u0637': 't',   # ط (toe)
    '\u0638': 'z',   # ظ (zoe)
    '\u0639': 'a',   # ع (ain) - often silent or vowel carrier
    '\u063a': 'gh',  # غ (ghain)
    '\u0641': 'f',   # ف (fe)
    '\u0642': 'q',   # ق (qaaf)
    '\u0643': 'k',   # ک (kaaf)
    '\u06af': 'g',   # گ (gaaf)
    '\u0644': 'l',   # ل (laam)
    '\u0645': 'm',   # م (meem)
    '\u0646': 'n',   # ن (noon)
    '\u0649': 'y',   # ی (chhoti ye)
    '\u064a': 'y',   # ي (baari ye)
    '\u0648': 'o',   # و (waaw) - often 'o' or 'u'
    '\u0647': 'h',   # ہ (chhoti he)
    '\u06c1': 'h',   # ہ (heh goal)
    '\u06cc': 'y',   # ی (chhoti ye)
    '\u06d2': 'e',   # ے (baari ye)
    '\u0621': '',    # ء (hamza)
    '\u0654': '',    # ◌ٔ (hamza above)
    '\u0655': '',    # ◌ٕ (hamza below)

    # Urdu digits
    '\u0660': '0',
    '\u0661': '1',
    '\u0662': '2',
    '\u0663': '3',
    '\u0664': '4',
    '\u0665': '5',
    '\u0666': '6',
    '\u0667': '7',
    '\u0668': '8',
    '\u0669': '9',
    '\u06f0': '0',
    '\u06f1': '1',
    '\u06f2': '2',
    '\u06f3': '3',
    '\u06f4': '4',
    '\u06f5': '5',
    '\u06f6': '6',
    '\u06f7': '7',
    '\u06f8': '8',
    '\u06f9': '9',

    # Diacritics (vowel signs) - often not rendered separately
    '\u064e': 'a',   # ◌َ (fatha/zabar)
    '\u064f': 'u',   # ◌ُ (damma/paish)
    '\u0650': 'i',   # ◌ِ (kasra/zer)
    '\u0651': '',    # ◌ّ (shadda)
    '\u0652': '',    # ◌ْ (sukun)
    '\u0670': 'aa',  # ◌ٰ (superscript alif)
}


# Cache for combined mapping
_HINGLISH_MAP = None


def _get_map():
    """Return the combined Devanagari + Urdu mapping dictionary."""
    global _HINGLISH_MAP
    if _HINGLISH_MAP is None:
        _HINGLISH_MAP = {}
        _HINGLISH_MAP.update(_DEVANAGARI_TO_HINGLISH)
        _HINGLISH_MAP.update(_URDU_TO_HINGLISH)
    return _HINGLISH_MAP


def transliterate_devanagari_to_hinglish(text: str) -> str:
    """
    Transliterate Devanagari (Hindi) text to Roman Hinglish.

    This is a presentation-layer transformation that does NOT affect
    lyric-note timing, alignment, or notation generation.

    Args:
        text: Hindi text in Devanagari script

    Returns:
        Romanized Hinglish string (e.g., "आपको है सारे समझने की" -> "Aapko hai saare samajhne ki")
    """
    if not text:
        return ""

    result = []
    i = 0
    map_dict = _get_map()

    while i < len(text):
        char = text[i]

        # Try to match longest possible sequence (2-char combos first)
        # Common Hindi digraphs and conjunct-like mappings
        if i + 1 < len(text):
            two_char = char + text[i + 1]
            if two_char in _HINGLISH_MAP:
                result.append(_HINGLISH_MAP[two_char])
                i += 2
                continue

        # Single character mapping
        if char in _HINGLISH_MAP:
            result.append(_HINGLISH_MAP[char])
        else:
            # For unmapped characters, preserve common punctuation/space
            if char.isspace():
                result.append(' ')
            elif char in '.,!?;:-\'"()[]{}':
                result.append(char)
            else:
                # Skip unmapped characters rather than adding '?'
                pass

        i += 1

    # Clean up: collapse multiple spaces, trim
    return ' '.join(''.join(result).split())


def transliterate_urdu_to_hinglish(text: str) -> str:
    """
    Transliterate Urdu/Arabic-script text to Roman Hinglish.

    Currently provides basic support for common Urdu words.
    Full Urdu support would require context-aware vowel marking.
    """
    if not text:
        return ""

    result = []
    map_dict = _get_map()

    for char in text:
        if char in map_dict:
            result.append(map_dict[char])
        else:
            if char.isspace():
                result.append(' ')
            elif char in '.,!?;:-\'"()[]{}':
                result.append(char)
            else:
                pass

    return ' '.join(''.join(result).split())


def is_devanagari_text(text: str) -> bool:
    """
    Check if text contains Devanagari (Hindi) characters.
    Returns True if the text is primarily in Hindi script.
    """
    if not text:
        return False

    devanagari_count = sum(1 for ch in text if 0x0900 <= ord(ch) <= 0x097F)
    # More than 30% Devanagari characters -> treat as Hindi text
    return (devanagari_count / max(len(text), 1)) > 0.3


def is_urdu_text(text: str) -> bool:
    """
    Check if text contains Urdu/Arabic-script characters.
    Returns True if the text is primarily in Urdu script.
    """
    if not text:
        return False

    urdu_count = sum(1 for ch in text if 0x0600 <= ord(ch) <= 0x06FF or 0x0750 <= ord(ch) <= 0x077F)
    # More than 30% Urdu/Arabic characters -> treat as Urdu text
    return (urdu_count / max(len(text), 1)) > 0.3


def transliterate_text(text: str) -> str:
    """
    Main entry point: auto-detect script and transliterate accordingly.

    Args:
        text: Lyric text that may be in Hindi (Devanagari), Urdu (Arabic),
              or already in Roman/Latin script

    Returns:
        Roman Hinglish transcription if non-Latin script detected,
        original text unchanged if already in Latin script
    """
    if not text:
        return ""

    # If already Latin script, return unchanged
    # Check if text contains primarily ASCII/English characters
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    if non_ascii / max(len(text), 1) < 0.3:
        # Less than 30% non-ASCII, likely English or mixed with mostly ASCII
        # Check if it's English words (just letters and spaces)
        letters_only = ''.join(ch for ch in text if ch.isalpha() or ch.isspace())
        if letters_only and (letters_only.isalpha() or letters_only.isspace()):
            return text  # Already English, don't alter

    # Check for Devanagari
    if is_devanagari_text(text):
        return transliterate_devanagari_to_hinglish(text)

    # Check for Urdu
    if is_urdu_text(text):
        return transliterate_urdu_to_hinglish(text)

    # Mixed or unknown script - try devanagari first, then return as-is
    if is_devanagari_text(text):
        return transliterate_devanagari_to_hinglish(text)

    return text