/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "modularity/imoduleinterface.h"
#include "global/async/channel.h"
#include "global/types/ret.h"
#include "actions/actiontypes.h"

namespace au::chat {

class IAgentActionExecutor : MODULE_EXPORT_INTERFACE
{
    INTERFACE_ID(IAgentActionExecutor)

public:
    virtual ~IAgentActionExecutor() = default;

    // Execute an action
    virtual muse::Ret executeAction(const muse::actions::ActionCode& code, 
                                     const muse::actions::ActionData& data = {}) = 0;

    // Check if action is enabled
    virtual bool isActionEnabled(const muse::actions::ActionCode& code) const = 0;

    // Get list of available actions
    virtual muse::actions::ActionCodeList availableActions() const = 0;

    // Notifications
    virtual muse::async::Channel<muse::actions::ActionCode> actionCompleted() const = 0;
    virtual muse::async::Channel<muse::actions::ActionCode, muse::Ret> actionFailed() const = 0;
};

}

