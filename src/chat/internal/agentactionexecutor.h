/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "iagentactionexecutor.h"
#include "modularity/ioc.h"
#include "async/asyncable.h"
#include "actions/iactionsdispatcher.h"
#include "trackedit/itrackeditactionscontroller.h"

namespace au::chat {

class AgentActionExecutor : public IAgentActionExecutor, public muse::async::Asyncable
{
    muse::Inject<muse::actions::IActionsDispatcher> dispatcher;
    muse::Inject<au::trackedit::ITrackeditActionsController> trackeditController;

public:
    AgentActionExecutor();
    ~AgentActionExecutor() override;

    void init();
    void deinit();

    muse::Ret executeAction(const muse::actions::ActionCode& code, 
                            const muse::actions::ActionData& data = {}) override;
    bool isActionEnabled(const muse::actions::ActionCode& code) const override;
    muse::actions::ActionCodeList availableActions() const override;

    muse::async::Channel<muse::actions::ActionCode> actionCompleted() const override;
    muse::async::Channel<muse::actions::ActionCode, muse::Ret> actionFailed() const override;

private:
    void onPreDispatch(const muse::actions::ActionCode& code);
    void onPostDispatch(const muse::actions::ActionCode& code);

    muse::async::Channel<muse::actions::ActionCode> m_actionCompleted;
    muse::async::Channel<muse::actions::ActionCode, muse::Ret> m_actionFailed;
};

}

