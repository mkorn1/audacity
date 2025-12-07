#!/usr/bin/env python3
"""
Location Parser Utility
Parses natural language time references into structured location data.

NOTE: This module provides comprehensive time parsing functionality.
Some basic time parsing is also available in value_inference.py as part
of the State Preparation system. This module can be used for more complex
parsing needs or as a standalone utility.
"""

import re
from typing import Dict, Any, Optional, Tuple


class LocationParser:
    """
    Parses location references from natural language.
    Handles explicit times, relative times, current state, and labels.
    """

    # Time format patterns
    TIME_PATTERNS = [
        (r'(\d+):(\d+):(\d+)', 'hms'),  # 2:15:30 (hours:minutes:seconds)
        (r'(\d+):(\d+)', 'ms'),  # 1:30 (minutes:seconds)
        (r'(\d+(?:\.\d+)?)\s*(?:seconds?|sec|s)\b', 'seconds'),  # 2s, 2 seconds, 2sec
        (r'(\d+(?:\.\d+)?)\s*(?:minutes?|min|m)\b', 'minutes'),  # 2m, 2 minutes
        (r'(\d+(?:\.\d+)?)\s*(?:hours?|hr|h)\b', 'hours'),  # 2h, 2 hours
        (r'(\d+(?:\.\d+)?)', 'seconds'),  # Bare number (assume seconds)
    ]

    @staticmethod
    def parse_time_string(time_str: str) -> Optional[float]:
        """
        Parse a time string into seconds.

        Args:
            time_str: Time string (e.g., "2:30", "90s", "1.5 minutes")

        Returns:
            Time in seconds, or None if invalid
        """
        time_str = time_str.strip().lower()

        for pattern, format_type in LocationParser.TIME_PATTERNS:
            match = re.search(pattern, time_str)
            if match:
                if format_type == 'hms':
                    hours, minutes, seconds = map(float, match.groups())
                    return hours * 3600 + minutes * 60 + seconds
                elif format_type == 'ms':
                    minutes, seconds = map(float, match.groups())
                    return minutes * 60 + seconds
                elif format_type == 'seconds':
                    return float(match.group(1))
                elif format_type == 'minutes':
                    return float(match.group(1)) * 60
                elif format_type == 'hours':
                    return float(match.group(1)) * 3600

        return None

    @staticmethod
    def parse_location(
        user_message: str,
        state_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse location references from user message.

        Args:
            user_message: User's message
            state_snapshot: Current state snapshot (for "current selection", "cursor", etc.)

        Returns:
            Dictionary with location information:
            {
                "type": "time_point" | "time_range" | "current_selection" | "cursor" | "label",
                "start_time": float (for range),
                "end_time": float (for range),
                "time": float (for point),
                "label_name": str (for label),
                "error": str (if parsing failed)
            }
        """
        user_message_lower = user_message.lower()

        # Check for "current selection" or "this" (when selection exists)
        if any(phrase in user_message_lower for phrase in ["current selection", "this selection", "the selection"]):
            if state_snapshot:
                start = state_snapshot.get("selection_start_time")
                end = state_snapshot.get("selection_end_time")
                has_selection = state_snapshot.get("has_time_selection", False)
                if has_selection and start is not None and end is not None:
                    return {
                        "type": "time_range",
                        "start_time": start,
                        "end_time": end
                    }
            return {"type": "error", "error": "No current selection available"}

        # Check for "at cursor" or "cursor"
        if any(phrase in user_message_lower for phrase in ["at cursor", "cursor", "playhead"]):
            if state_snapshot:
                cursor = state_snapshot.get("cursor_position")
                if cursor is not None:
                    return {
                        "type": "time_point",
                        "time": cursor
                    }
            return {"type": "error", "error": "Cursor position not available"}

        # Check for "from X to Y" pattern
        from_to_match = re.search(
            r'from\s+([^\s]+(?:\s+[^\s]+)*?)\s+to\s+([^\s]+(?:\s+[^\s]+)*?)(?:\s|$|,|\.)',
            user_message_lower
        )
        if from_to_match:
            start_str = from_to_match.group(1).strip()
            end_str = from_to_match.group(2).strip()
            start_time = LocationParser.parse_time_string(start_str)
            end_time = LocationParser.parse_time_string(end_str)
            if start_time is not None and end_time is not None:
                return {
                    "type": "time_range",
                    "start_time": start_time,
                    "end_time": end_time
                }

        # Check for "first N seconds" or "first N"
        first_match = re.search(r'first\s+([^\s]+(?:\s+[^\s]+)*?)(?:\s|$|,|\.)', user_message_lower)
        if first_match:
            time_str = first_match.group(1).strip()
            end_time = LocationParser.parse_time_string(time_str)
            if end_time is not None:
                return {
                    "type": "time_range",
                    "start_time": 0.0,
                    "end_time": end_time
                }

        # Check for "last N seconds" or "last N"
        last_match = re.search(r'last\s+([^\s]+(?:\s+[^\s]+)*?)(?:\s|$|,|\.)', user_message_lower)
        if last_match:
            time_str = last_match.group(1).strip()
            duration = LocationParser.parse_time_string(time_str)
            if duration is not None and state_snapshot:
                total_time = state_snapshot.get("total_project_time", 0.0)
                if total_time > 0:
                    return {
                        "type": "time_range",
                        "start_time": max(0.0, total_time - duration),
                        "end_time": total_time
                    }
            return {"type": "error", "error": "Cannot calculate 'last N seconds' without project duration"}

        # Check for "at X" or "X" (time point)
        at_match = re.search(r'at\s+([^\s]+(?:\s+[^\s]+)*?)(?:\s|$|,|\.)', user_message_lower)
        if at_match:
            time_str = at_match.group(1).strip()
            time = LocationParser.parse_time_string(time_str)
            if time is not None:
                return {
                    "type": "time_point",
                    "time": time
                }

        # Check for label references (e.g., "intro", "outro")
        # This is a simple heuristic - could be enhanced with actual label matching
        label_keywords = ["intro", "outro", "chapter", "segment", "part"]
        for keyword in label_keywords:
            if keyword in user_message_lower:
                if state_snapshot:
                    labels = state_snapshot.get("all_labels", [])
                    # Try to find matching label
                    for label in labels:
                        label_name = label.get("name", "").lower()
                        if keyword in label_name or label_name in keyword:
                            start = label.get("start_time")
                            end = label.get("end_time")
                            if start is not None and end is not None:
                                return {
                                    "type": "time_range",
                                    "start_time": start,
                                    "end_time": end,
                                    "label_name": label.get("name")
                                }
                return {"type": "error", "error": f"Label '{keyword}' not found"}

        # Try to parse as bare time range "X to Y" or "X-Y"
        range_match = re.search(
            r'(\d+(?:\.\d+)?(?::\d+(?:\.\d+)?)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?(?::\d+(?:\.\d+)?)?)',
            user_message_lower
        )
        if range_match:
            start_str = range_match.group(1).strip()
            end_str = range_match.group(2).strip()
            start_time = LocationParser.parse_time_string(start_str)
            end_time = LocationParser.parse_time_string(end_str)
            if start_time is not None and end_time is not None:
                return {
                    "type": "time_range",
                    "start_time": start_time,
                    "end_time": end_time
                }

        # Try to parse as single time point
        time_match = re.search(
            r'(\d+(?:\.\d+)?(?::\d+(?:\.\d+)?)?)(?:\s|$|,|\.)',
            user_message_lower
        )
        if time_match:
            time_str = time_match.group(1).strip()
            time = LocationParser.parse_time_string(time_str)
            if time is not None:
                return {
                    "type": "time_point",
                    "time": time
                }

        return {"type": "error", "error": "Could not parse location from message"}

    @staticmethod
    def find_label_by_name(
        label_name: str,
        state_snapshot: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find a label by name (case-insensitive, partial match).

        Args:
            label_name: Label name to find
            state_snapshot: State snapshot with labels

        Returns:
            Label dictionary with 'name', 'start_time', 'end_time', or None
        """
        if not state_snapshot:
            return None

        labels = state_snapshot.get("all_labels", [])
        label_name_lower = label_name.lower()

        # Try exact match first
        for label in labels:
            if label.get("name", "").lower() == label_name_lower:
                return label

        # Try partial match
        for label in labels:
            label_name_check = label.get("name", "").lower()
            if label_name_lower in label_name_check or label_name_check in label_name_lower:
                return label

        return None

