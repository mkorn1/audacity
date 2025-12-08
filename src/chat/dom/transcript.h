/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include <vector>
#include <optional>

#include "global/types/string.h"

namespace au::chat {
struct TranscriptWord {
    muse::String word;
    double startTime = 0.0;  // in seconds
    double endTime = 0.0;    // in seconds
    double confidence = 0.0;
    bool isFiller = false;
    std::optional<muse::String> speaker;  // Optional speaker ID for diarization
};

struct TranscriptUtterance {
    muse::String text;
    double startTime = 0.0;
    double endTime = 0.0;
    std::optional<muse::String> speaker;
    std::vector<TranscriptWord> words;
};

struct Transcript {
    std::vector<TranscriptUtterance> utterances;
    std::vector<TranscriptWord> words;
    muse::String fullText;
    double duration = 0.0;
    int fillerCount = 0;

    inline bool isValid() const { return !words.empty() && duration > 0.0; }
    inline bool isEmpty() const { return words.empty(); }
};

using TranscriptWords = std::vector<TranscriptWord>;
using TranscriptUtterances = std::vector<TranscriptUtterance>;
}

