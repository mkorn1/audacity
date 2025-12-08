/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "modularity/imoduleinterface.h"
#include "dom/transcript.h"
#include "global/async/channel.h"
#include "global/async/notification.h"

namespace au::chat {
class ITranscriptService : MODULE_EXPORT_INTERFACE
{
    INTERFACE_ID(ITranscriptService)

public:
    virtual ~ITranscriptService() = default;

    // Get current transcript
    virtual Transcript transcript() const = 0;
    virtual bool hasTranscript() const = 0;

    // Set transcript (called from Python bridge)
    virtual void setTranscript(const Transcript& transcript) = 0;
    virtual void clearTranscript() = 0;

    // Get words/utterances in time range (for rendering visible items)
    virtual TranscriptWords wordsInRange(double startTime, double endTime) const = 0;
    virtual TranscriptUtterances utterancesInRange(double startTime, double endTime) const = 0;

    // Signals
    virtual muse::async::Channel<Transcript> transcriptChanged() const = 0;
    virtual muse::async::Notification transcriptCleared() const = 0;
};
}

