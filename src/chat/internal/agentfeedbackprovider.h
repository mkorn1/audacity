/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "iagentfeedbackprovider.h"
#include "modularity/ioc.h"
#include "async/asyncable.h"
#include "actions/iactionsdispatcher.h"

namespace au::chat {

class AgentFeedbackProvider : public IAgentFeedbackProvider, public muse::async::Asyncable
{
    muse::Inject<muse::actions::IActionsDispatcher> dispatcher;

public:
    AgentFeedbackProvider();
    ~AgentFeedbackProvider() override;

    void init();

    void highlightSelection(const SelectionHighlight& highlight) override;
    void clearHighlights() override;

    void showProgress(const std::string& message, double progress = 0.0) override;
    void hideProgress() override;

    void showDialog(const std::string& dialogType, const std::string& params = "") override;
    void hideDialog() override;

    muse::async::Channel<std::string> feedbackMessage() const override;

private:
    void onPreDispatch(const muse::actions::ActionCode& code);
    void onPostDispatch(const muse::actions::ActionCode& code);

    SelectionHighlight m_currentHighlight;
    bool m_hasHighlight = false;
    std::string m_currentProgressMessage;
    bool m_hasProgress = false;

    muse::async::Channel<std::string> m_feedbackMessage;
};

}

