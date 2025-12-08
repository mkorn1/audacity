/*
* Audacity: A Digital Audio Editor
*/
#include "transcriptservice.h"

#include "log.h"

using namespace au::chat;

Transcript TranscriptService::transcript() const
{
    return m_transcript;
}

bool TranscriptService::hasTranscript() const
{
    return m_transcript.isValid();
}

void TranscriptService::setTranscript(const Transcript& transcript)
{
    m_transcript = transcript;
    m_transcriptChanged.send(m_transcript);
}

void TranscriptService::clearTranscript()
{
    m_transcript = Transcript();
    m_transcriptCleared.notify();
}

TranscriptWords TranscriptService::wordsInRange(double startTime, double endTime) const
{
    TranscriptWords result;
    for (const auto& word : m_transcript.words) {
        // Include words that overlap with the range
        if (word.endTime >= startTime && word.startTime <= endTime) {
            result.push_back(word);
        }
    }
    return result;
}

TranscriptUtterances TranscriptService::utterancesInRange(double startTime, double endTime) const
{
    TranscriptUtterances result;
    for (const auto& utterance : m_transcript.utterances) {
        // Include utterances that overlap with the range
        if (utterance.endTime >= startTime && utterance.startTime <= endTime) {
            result.push_back(utterance);
        }
    }
    return result;
}

muse::async::Channel<Transcript> TranscriptService::transcriptChanged() const
{
    return m_transcriptChanged;
}

muse::async::Notification TranscriptService::transcriptCleared() const
{
    return m_transcriptCleared;
}

