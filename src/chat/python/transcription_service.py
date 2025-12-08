#!/usr/bin/env python3
"""
Transcription service using AssemblyAI API.
Provides verbatim transcription with filler words preserved and word-level timestamps.

AssemblyAI features used:
- disfluencies=true: Keeps filler words (um, uh, etc.)
- Word-level timestamps included by default
- Speaker diarization (optional)
"""

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pathlib import Path

import requests

from config import get_config_value


@dataclass
class TranscriptWord:
    """A single word in the transcript with timing information."""
    word: str
    start_time: float  # in seconds
    end_time: float    # in seconds
    confidence: float
    is_filler: bool = False
    speaker: Optional[str] = None


@dataclass
class TranscriptUtterance:
    """A segment of speech (sentence/phrase) with timing and speaker info."""
    text: str
    start_time: float
    end_time: float
    speaker: Optional[str] = None
    words: List[TranscriptWord] = field(default_factory=list)


@dataclass
class Transcript:
    """Complete transcript with utterances and word-level data."""
    utterances: List[TranscriptUtterance]
    words: List[TranscriptWord]
    full_text: str
    duration: float

    # Filler word summary
    filler_words: List[TranscriptWord] = field(default_factory=list)
    filler_count: int = 0


class TranscriptionService:
    """
    Service for transcribing audio using AssemblyAI API.

    Features:
    - Word-level timestamps
    - Filler word preservation (um, uh, like, you know, etc.) via disfluencies=true
    - Speaker diarization (optional)
    """

    # Base API endpoints
    UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
    TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"

    # Common filler words to identify
    FILLER_WORDS = {
        "um", "uh", "uhm", "umm", "uhh", "ah", "er", "err",
        "like", "you know", "i mean", "actually", "basically",
        "literally", "right", "so", "well", "okay", "ok", "mm", "hmm"
    }

    # Single-word fillers for quick lookup
    SINGLE_WORD_FILLERS = {
        "um", "uh", "uhm", "umm", "uhh", "ah", "er", "err",
        "like", "actually", "basically", "literally", "right",
        "so", "well", "okay", "ok", "mm", "hmm", "mhm", "uh-huh"
    }

    def __init__(self):
        self.api_key = get_config_value("ASSEMBLYAI_API_KEY", "")

    def is_configured(self) -> bool:
        """Check if AssemblyAI API key is configured."""
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        """Get API headers with authorization."""
        return {"authorization": self.api_key}

    def transcribe_file(
        self,
        audio_path: str,
        enable_diarization: bool = False,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Transcribe an audio file.

        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)
            enable_diarization: Enable speaker diarization
            language: Language code (default: "en")

        Returns:
            Dict with transcript data or error
        """
        if not self.api_key:
            return {"error": "ASSEMBLYAI_API_KEY not configured"}

        audio_path = Path(audio_path)
        if not audio_path.exists():
            return {"error": f"Audio file not found: {audio_path}"}

        try:
            # Step 1: Upload the audio file
            print(f"Uploading audio file: {audio_path}", file=sys.stderr)
            upload_url = self._upload_file(audio_path)
            if not upload_url:
                return {"error": "Failed to upload audio file"}

            # Step 2: Request transcription
            print("Requesting transcription...", file=sys.stderr)
            transcript_id = self._request_transcription(
                upload_url,
                enable_diarization=enable_diarization,
                language=language
            )
            if not transcript_id:
                return {"error": "Failed to start transcription"}

            # Step 3: Poll for completion
            print("Waiting for transcription to complete...", file=sys.stderr)
            result = self._poll_for_completion(transcript_id)
            if not result:
                return {"error": "Transcription failed or timed out"}

            if result.get("status") == "error":
                return {"error": result.get("error", "Transcription failed")}

            # Step 4: Process the response
            return self._process_response(result)

        except requests.exceptions.Timeout:
            return {"error": "Transcription request timed out"}
        except requests.exceptions.RequestException as e:
            return {"error": f"Network error: {str(e)}"}
        except Exception as e:
            return {"error": f"Transcription failed: {str(e)}"}

    def _wait_for_file_stable(self, audio_path: Path, timeout: int = 30) -> bool:
        """
        Wait for file to stabilize (stop growing).

        The Audacity export runs asynchronously, so the file may still be
        written when we first check it. This waits until the file size
        stops changing for at least 1 second.
        """
        start_time = time.time()
        last_size = -1
        stable_count = 0

        while time.time() - start_time < timeout:
            if not audio_path.exists():
                time.sleep(0.5)
                continue

            current_size = audio_path.stat().st_size

            if current_size == last_size and current_size > 0:
                stable_count += 1
                if stable_count >= 2:  # Size unchanged for 2 checks (~1 second)
                    print(f"File stabilized at {current_size} bytes", file=sys.stderr)
                    return True
            else:
                stable_count = 0

            last_size = current_size
            time.sleep(0.5)

        print(f"File did not stabilize within {timeout}s", file=sys.stderr)
        return False

    def _upload_file(self, audio_path: Path) -> Optional[str]:
        """Upload audio file to AssemblyAI and return the upload URL."""
        headers = self._get_headers()

        # Wait for export to complete - file must stabilize
        if not self._wait_for_file_stable(audio_path):
            print("Error: Export did not complete in time", file=sys.stderr)
            return None

        # Check file size
        file_size = audio_path.stat().st_size
        print(f"Audio file size: {file_size} bytes", file=sys.stderr)

        if file_size == 0:
            print("Error: Audio file is empty", file=sys.stderr)
            return None

        if file_size < 1000:
            print(f"Warning: Audio file is very small ({file_size} bytes)", file=sys.stderr)

        with open(audio_path, "rb") as f:
            response = requests.post(
                self.UPLOAD_URL,
                headers=headers,
                data=f,
                timeout=300
            )

        if response.status_code == 200:
            return response.json().get("upload_url")
        else:
            print(f"Upload failed: {response.status_code} - {response.text}", file=sys.stderr)
            return None

    def _request_transcription(
        self,
        audio_url: str,
        enable_diarization: bool = False,
        language: str = "en"
    ) -> Optional[str]:
        """Request transcription and return transcript ID."""
        headers = self._get_headers()
        headers["content-type"] = "application/json"

        data = {
            "audio_url": audio_url,
            "language_code": language,
            "disfluencies": True,  # Keep filler words!
        }

        if enable_diarization:
            data["speaker_labels"] = True

        response = requests.post(
            self.TRANSCRIPT_URL,
            headers=headers,
            json=data,
            timeout=30
        )

        if response.status_code == 200:
            return response.json().get("id")
        else:
            print(f"Transcription request failed: {response.status_code} - {response.text}", file=sys.stderr)
            return None

    def _poll_for_completion(
        self,
        transcript_id: str,
        max_wait: int = 600,
        poll_interval: int = 5
    ) -> Optional[Dict]:
        """Poll for transcription completion."""
        headers = self._get_headers()
        url = f"{self.TRANSCRIPT_URL}/{transcript_id}"

        start_time = time.time()
        while time.time() - start_time < max_wait:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                print(f"Poll failed: {response.status_code}", file=sys.stderr)
                return None

            result = response.json()
            status = result.get("status")

            if status == "completed":
                return result
            elif status == "error":
                return result
            elif status in ("queued", "processing"):
                time.sleep(poll_interval)
            else:
                print(f"Unknown status: {status}", file=sys.stderr)
                time.sleep(poll_interval)

        return None  # Timed out

    def _process_response(self, api_result: Dict) -> Dict[str, Any]:
        """
        Process AssemblyAI API response into our transcript format.

        Args:
            api_result: Raw AssemblyAI API response

        Returns:
            Processed transcript dict
        """
        try:
            words_data = api_result.get("words", [])
            utterances_data = api_result.get("utterances", [])
            full_text = api_result.get("text", "")
            duration = api_result.get("audio_duration", 0.0)

            # Process all words
            all_words: List[TranscriptWord] = []
            filler_words: List[TranscriptWord] = []

            for w in words_data:
                word_text = w.get("text", "")
                word_lower = word_text.lower().strip()
                is_filler = word_lower in self.SINGLE_WORD_FILLERS

                # Convert milliseconds to seconds
                start_ms = w.get("start", 0)
                end_ms = w.get("end", 0)

                word = TranscriptWord(
                    word=word_text,
                    start_time=start_ms / 1000.0,
                    end_time=end_ms / 1000.0,
                    confidence=w.get("confidence", 0.0),
                    is_filler=is_filler,
                    speaker=w.get("speaker")
                )

                all_words.append(word)
                if is_filler:
                    filler_words.append(word)

            # Process utterances (if speaker diarization was enabled)
            utterances: List[TranscriptUtterance] = []
            if utterances_data:
                for utt in utterances_data:
                    start_ms = utt.get("start", 0)
                    end_ms = utt.get("end", 0)

                    # Get words for this utterance
                    utt_words = [
                        w for w in all_words
                        if w.start_time >= start_ms / 1000.0 and w.end_time <= end_ms / 1000.0
                    ]

                    utterance = TranscriptUtterance(
                        text=utt.get("text", ""),
                        start_time=start_ms / 1000.0,
                        end_time=end_ms / 1000.0,
                        speaker=utt.get("speaker"),
                        words=utt_words
                    )
                    utterances.append(utterance)
            else:
                # No utterances data - create a single utterance from all words
                if all_words:
                    utterance = TranscriptUtterance(
                        text=full_text,
                        start_time=all_words[0].start_time if all_words else 0,
                        end_time=all_words[-1].end_time if all_words else 0,
                        speaker=None,
                        words=all_words
                    )
                    utterances.append(utterance)

            # Create transcript object
            transcript = Transcript(
                utterances=utterances,
                words=all_words,
                full_text=full_text,
                duration=duration,
                filler_words=filler_words,
                filler_count=len(filler_words)
            )

            return {
                "success": True,
                "transcript": self._transcript_to_dict(transcript)
            }

        except Exception as e:
            return {"error": f"Failed to process response: {str(e)}"}

    def _transcript_to_dict(self, transcript: Transcript) -> Dict[str, Any]:
        """Convert Transcript dataclass to dict for JSON serialization."""
        return {
            "utterances": [
                {
                    "text": u.text,
                    "start_time": u.start_time,
                    "end_time": u.end_time,
                    "speaker": u.speaker,
                    "words": [self._word_to_dict(w) for w in u.words]
                }
                for u in transcript.utterances
            ],
            "words": [self._word_to_dict(w) for w in transcript.words],
            "full_text": transcript.full_text,
            "duration": transcript.duration,
            "filler_words": [self._word_to_dict(w) for w in transcript.filler_words],
            "filler_count": transcript.filler_count
        }

    def _word_to_dict(self, word: TranscriptWord) -> Dict[str, Any]:
        """Convert TranscriptWord dataclass to dict."""
        return {
            "word": word.word,
            "start_time": word.start_time,
            "end_time": word.end_time,
            "confidence": word.confidence,
            "is_filler": word.is_filler,
            "speaker": word.speaker
        }

    def search_transcript(
        self,
        transcript: Dict[str, Any],
        query: str,
        case_sensitive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search transcript for a word or phrase.

        Args:
            transcript: Transcript dict from transcribe_file()
            query: Text to search for
            case_sensitive: Whether search is case-sensitive

        Returns:
            List of matches with time ranges
        """
        matches = []

        if not case_sensitive:
            query = query.lower()

        words = transcript.get("words", [])
        utterances = transcript.get("utterances", [])

        # Search individual words
        for word in words:
            word_text = word["word"] if case_sensitive else word["word"].lower()
            if query == word_text:
                matches.append({
                    "text": word["word"],
                    "start_time": word["start_time"],
                    "end_time": word["end_time"],
                    "match_type": "word",
                    "confidence": word["confidence"],
                    "speaker": word.get("speaker")
                })

        # Search phrases in utterances
        query_words = query.split()
        if len(query_words) > 1:
            for utt in utterances:
                utt_text = utt["text"] if case_sensitive else utt["text"].lower()
                if query in utt_text:
                    # Find the specific word range for the match
                    match_info = self._find_phrase_in_utterance(
                        utt, query, case_sensitive
                    )
                    if match_info:
                        matches.append(match_info)

        return matches

    def _find_phrase_in_utterance(
        self,
        utterance: Dict[str, Any],
        query: str,
        case_sensitive: bool
    ) -> Optional[Dict[str, Any]]:
        """Find a phrase within an utterance and return timing info."""
        words = utterance.get("words", [])
        query_words = query.lower().split() if not case_sensitive else query.split()
        query_len = len(query_words)

        for i in range(len(words) - query_len + 1):
            window = words[i:i + query_len]
            window_text = [
                w["word"].lower() if not case_sensitive else w["word"]
                for w in window
            ]

            if window_text == query_words:
                return {
                    "text": " ".join(w["word"] for w in window),
                    "start_time": window[0]["start_time"],
                    "end_time": window[-1]["end_time"],
                    "match_type": "phrase",
                    "speaker": utterance.get("speaker")
                }

        return None

    def get_filler_words(
        self,
        transcript: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get all filler words from the transcript with summary.

        Args:
            transcript: Transcript dict from transcribe_file()

        Returns:
            Dict with filler words and summary statistics
        """
        filler_words = transcript.get("filler_words", [])

        # Count by filler type
        counts: Dict[str, int] = {}
        for fw in filler_words:
            word = fw["word"].lower()
            counts[word] = counts.get(word, 0) + 1

        # Sort by frequency
        sorted_counts = sorted(counts.items(), key=lambda x: -x[1])

        # Calculate filler density (fillers per minute)
        duration = transcript.get("duration", 0)
        fillers_per_minute = (
            len(filler_words) / (duration / 60) if duration > 0 else 0
        )

        return {
            "success": True,
            "filler_words": filler_words,
            "count": len(filler_words),
            "by_type": dict(sorted_counts),
            "fillers_per_minute": round(fillers_per_minute, 2),
            "summary": ", ".join(
                f"{word}: {count}" for word, count in sorted_counts[:5]
            )
        }


# Module-level convenience functions
_service: Optional[TranscriptionService] = None


def get_transcription_service() -> TranscriptionService:
    """Get or create the singleton transcription service."""
    global _service
    if _service is None:
        _service = TranscriptionService()
    return _service


def transcribe_audio(audio_path: str, **kwargs) -> Dict[str, Any]:
    """Convenience function to transcribe an audio file."""
    return get_transcription_service().transcribe_file(audio_path, **kwargs)


def search_transcript(transcript: Dict, query: str, **kwargs) -> List[Dict]:
    """Convenience function to search a transcript."""
    return get_transcription_service().search_transcript(transcript, query, **kwargs)


def get_filler_words(transcript: Dict) -> Dict[str, Any]:
    """Convenience function to get filler words from a transcript."""
    return get_transcription_service().get_filler_words(transcript)
