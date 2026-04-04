"""
Postprocessor
=============
Cleans up Whisper's raw transcription output for Nigerian English context.

Pipeline position:
    [transcriber] → postprocessor → [Redis output to NLP engine]

Handles:
- Common Whisper misrecognitions of Nigerian English words/phrases
- Filler word removal (optional, configurable)
- Basic text normalization (whitespace, casing)
- Preparing clean text for Amos's NLP engine to convert to sign language gloss
"""

import re


# ---------------------------------------------------------------------------
# Nigerian English correction map
# ---------------------------------------------------------------------------
# Whisper sometimes mishears Nigerian English expressions, Pidgin words, and
# accent-influenced pronunciations. This map catches the most common ones.
#
# Format: {wrong_transcription: correct_form}
# Add more as you discover patterns during testing with Nigerian speakers.
NIGERIAN_CORRECTIONS = {
    # Common Pidgin/colloquial that Whisper misinterprets
    "abbey": "abi",          # "abi" = Nigerian "right?" / confirmation tag
    "shah": "sha",           # "sha" = "anyway" / emphasis particle
    "share": "sha",          # alternate mishearing
    "oh boy": "o boy",       # exclamation
    "way tin": "wetin",      # "wetin" = "what"
    "way team": "wetin",
    "no wahala": "no wahala", # already correct but ensure consistency
    "walahi": "wallahi",     # "wallahi" = "I swear" (Hausa origin)
    "walla he": "wallahi",
    "well i he": "wallahi",
    "a beg": "abeg",         # "abeg" = "please"
    "shay": "shey",          # "shey" = "isn't it?" / question tag
    "shea": "shey",
    "chale": "shey",         # possible misrecognition

    # Common Nigerian name mishearings (extend with your team's test data)
    "ola wall": "olawale",
    "chee nelo": "chinelo",
    "in yam ah": "inyama",
}

# Filler words common in Nigerian English speech.
# These add no meaning and would confuse the NLP → sign language pipeline.
# Set REMOVE_FILLERS = True to strip them.
FILLER_WORDS = [
    "erm", "uhm", "um", "uh", "eh", "ehn",
    "like like", "you know", "you understand",
]

REMOVE_FILLERS = True


class Postprocessor:

    def clean_text(self, text: str) -> str:
        """
        Full postprocessing pipeline for a transcription string.

        Args:
            text: Raw text from Whisper transcriber

        Returns:
            Cleaned, normalized text ready for the NLP engine
        """
        if not text or not text.strip():
            return ""

        text = text.strip()

        # Step 1: Normalize whitespace
        text = self._normalize_whitespace(text)

        # Step 2: Apply Nigerian English corrections
        text = self._apply_corrections(text)

        # Step 3: Remove filler words (if enabled)
        if REMOVE_FILLERS:
            text = self._remove_fillers(text)

        # Step 4: Fix punctuation spacing
        text = self._fix_punctuation(text)

        # Step 5: Final cleanup
        text = text.strip()

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Collapse multiple spaces/tabs/newlines into single spaces."""
        return re.sub(r"\s+", " ", text)

    def _apply_corrections(self, text: str) -> str:
        """
        Replace known Whisper misrecognitions with correct Nigerian English forms.
        Uses case-insensitive matching to catch variations.
        """
        lower_text = text.lower()
        for wrong, correct in NIGERIAN_CORRECTIONS.items():
            # Word boundary matching to avoid replacing parts of other words
            pattern = re.compile(r"\b" + re.escape(wrong) + r"\b", re.IGNORECASE)
            # Preserve original casing style: if original was capitalized, capitalize correction
            if text[0:1].isupper() and lower_text.startswith(wrong):
                replacement = correct.capitalize()
            else:
                replacement = correct
            text = pattern.sub(replacement, text)

        return text

    def _remove_fillers(self, text: str) -> str:
        """Remove filler words/phrases that add no meaning for sign language."""
        for filler in FILLER_WORDS:
            pattern = re.compile(r"\b" + re.escape(filler) + r"\b", re.IGNORECASE)
            text = pattern.sub("", text)

        # Clean up any double spaces left behind
        text = re.sub(r"\s+", " ", text)
        return text

    def _fix_punctuation(self, text: str) -> str:
        """Fix common punctuation issues (spaces before periods, double periods, etc.)."""
        # Remove space before punctuation
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        # Remove double punctuation
        text = re.sub(r"([.,!?;:]){2,}", r"\1", text)
        return text
