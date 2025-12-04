/*
* Audacity: A Digital Audio Editor
*/
#include "agentfeedbackprovider.h"

#include "global/log.h"
#include "trackedit/iselectioncontroller.h"
#include "modularity/ioc.h"

using namespace au::chat;
using namespace muse;
using namespace muse::actions;

AgentFeedbackProvider::AgentFeedbackProvider()
{
}

AgentFeedbackProvider::~AgentFeedbackProvider()
{
}

void AgentFeedbackProvider::init()
{
    // Subscribe to action dispatcher for visual feedback
    dispatcher()->preDispatch().onReceive(this, [this](const ActionCode& code) {
        onPreDispatch(code);
    });

    dispatcher()->postDispatch().onReceive(this, [this](const ActionCode& code) {
        onPostDispatch(code);
    });
}

void AgentFeedbackProvider::highlightSelection(const SelectionHighlight& highlight)
{
    m_currentHighlight = highlight;
    m_hasHighlight = true;

    // Apply highlights through selection controller
    auto selectionController = muse::modularity::_ioc()->resolve<au::trackedit::ISelectionController>("trackedit");
    if (selectionController) {
        if (!highlight.trackIds.empty()) {
            selectionController->setSelectedTracks(highlight.trackIds, true);
        }
        if (!highlight.clipKeys.empty()) {
            selectionController->setSelectedClips(highlight.clipKeys, true);
        }
        if (highlight.startTime.to_double() >= 0.0 && highlight.endTime.to_double() > highlight.startTime.to_double()) {
            selectionController->setDataSelectedStartTime(highlight.startTime, false);
            selectionController->setDataSelectedEndTime(highlight.endTime, true);
        }
    }

    m_feedbackMessage.send("Selection highlighted");
}

void AgentFeedbackProvider::clearHighlights()
{
    m_hasHighlight = false;
    m_currentHighlight = SelectionHighlight();

    auto selectionController = muse::modularity::_ioc()->resolve<au::trackedit::ISelectionController>("trackedit");
    if (selectionController) {
        selectionController->resetDataSelection();
        selectionController->resetSelectedClips();
    }

    m_feedbackMessage.send("Highlights cleared");
}

void AgentFeedbackProvider::showProgress(const std::string& message, double progress)
{
    m_currentProgressMessage = message;
    m_hasProgress = true;
    m_feedbackMessage.send(message + " (" + std::to_string(int(progress * 100)) + "%)");
}

void AgentFeedbackProvider::hideProgress()
{
    m_hasProgress = false;
    m_currentProgressMessage.clear();
}

void AgentFeedbackProvider::showDialog(const std::string& dialogType, const std::string& params)
{
    // Dialog opening is handled by the action dispatcher
    // This is mainly for logging/feedback
    LOGI() << "AgentFeedbackProvider: Showing dialog: " << dialogType;
    m_feedbackMessage.send("Opening " + dialogType + " dialog");
}

void AgentFeedbackProvider::hideDialog()
{
    m_feedbackMessage.send("Dialog closed");
}

muse::async::Channel<std::string> AgentFeedbackProvider::feedbackMessage() const
{
    return m_feedbackMessage;
}

void AgentFeedbackProvider::onPreDispatch(const ActionCode& code)
{
    // Provide visual feedback when actions start
    std::string feedback = "Executing: " + code;
    m_feedbackMessage.send(feedback);
}

void AgentFeedbackProvider::onPostDispatch(const ActionCode& code)
{
    // Provide visual feedback when actions complete
    std::string feedback = "Completed: " + code;
    m_feedbackMessage.send(feedback);
}

