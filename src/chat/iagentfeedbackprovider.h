/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "modularity/imoduleinterface.h"
#include "global/async/channel.h"
#include "trackedit/trackedittypes.h"

namespace au::chat {

struct SelectionHighlight {
    trackedit::TrackIdList trackIds;
    trackedit::ClipKeyList clipKeys;
    trackedit::secs_t startTime = 0.0;
    trackedit::secs_t endTime = 0.0;
};

class IAgentFeedbackProvider : MODULE_EXPORT_INTERFACE
{
    INTERFACE_ID(IAgentFeedbackProvider)

public:
    virtual ~IAgentFeedbackProvider() = default;

    // Highlight selections
    virtual void highlightSelection(const SelectionHighlight& highlight) = 0;
    virtual void clearHighlights() = 0;

    // Show progress
    virtual void showProgress(const std::string& message, double progress = 0.0) = 0;
    virtual void hideProgress() = 0;

    // Show dialog (for effects, etc.)
    virtual void showDialog(const std::string& dialogType, const std::string& params = "") = 0;
    virtual void hideDialog() = 0;

    // Notifications
    virtual muse::async::Channel<std::string> feedbackMessage() const = 0;
};

}

