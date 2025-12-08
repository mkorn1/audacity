/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "itranscriptservice.h"

namespace au::chat {
class TranscriptService : public ITranscriptService
{
public:
    TranscriptService() = default;

    Transcript transcript() const override;
    bool hasTranscript() const override;

    void setTranscript(const Transcript& transcript) override;
    void clearTranscript() override;

    TranscriptWords wordsInRange(double startTime, double endTime) const override;
    TranscriptUtterances utterancesInRange(double startTime, double endTime) const override;

    muse::async::Channel<Transcript> transcriptChanged() const override;
    muse::async::Notification transcriptCleared() const override;

private:
    Transcript m_transcript;
    mutable muse::async::Channel<Transcript> m_transcriptChanged;
    mutable muse::async::Notification m_transcriptCleared;
};
}

