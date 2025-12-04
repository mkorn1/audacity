/*
* Audacity: A Digital Audio Editor
*/
#include "agentactionexecutor.h"

#include "global/log.h"
#include "global/types/ret.h"

using namespace au::chat;
using namespace muse;
using namespace muse::actions;

AgentActionExecutor::AgentActionExecutor()
{
}

AgentActionExecutor::~AgentActionExecutor()
{
}

void AgentActionExecutor::init()
{
    // Subscribe to action dispatcher events for feedback
    dispatcher()->preDispatch().onReceive(this, [this](const ActionCode& code) {
        onPreDispatch(code);
    });

    dispatcher()->postDispatch().onReceive(this, [this](const ActionCode& code) {
        onPostDispatch(code);
    });
}

void AgentActionExecutor::deinit()
{
    // Subscriptions are automatically cleaned up by Asyncable destructor
}

muse::Ret AgentActionExecutor::executeAction(const ActionCode& code, const ActionData& data)
{
    // Validate action is enabled
    if (!isActionEnabled(code)) {
        LOGW() << "Action not enabled: " << code;
        Ret ret = make_ret(Ret::Code::InternalError, "Action not enabled: " + code);
        m_actionFailed.send(code, ret);
        return ret;
    }

    // Check if action is registered
    auto available = availableActions();
    if (std::find(available.begin(), available.end(), code) == available.end()) {
        LOGW() << "Action not registered: " << code;
        Ret ret = make_ret(Ret::Code::InternalError, "Action not registered: " + code);
        m_actionFailed.send(code, ret);
        return ret;
    }

    // Dispatch the action
    LOGI() << "AgentActionExecutor: Executing action: " << code;
    dispatcher()->dispatch(code, data);

    // Note: We rely on postDispatch channel to know when action completes
    // For now, assume success if no error occurs immediately
    return make_ret(Ret::Code::Ok);
}

bool AgentActionExecutor::isActionEnabled(const ActionCode& code) const
{
    // Check with trackedit controller if it's a trackedit action
    if (code.find("trackedit") != std::string::npos || 
        code.find("split") != std::string::npos ||
        code.find("join") != std::string::npos ||
        code.find("clip-") != std::string::npos ||
        code.find("track-") != std::string::npos) {
        // return trackeditController()->actionEnabled(code);  // Temporarily disabled
        return true;  // Default to enabled for now
    }

    // For other actions, assume enabled if registered
    // TODO: Add more specific checks for other action types
    return true;
}

ActionCodeList AgentActionExecutor::availableActions() const
{
    return dispatcher()->actionList();
}

muse::async::Channel<ActionCode> AgentActionExecutor::actionCompleted() const
{
    return m_actionCompleted;
}

muse::async::Channel<ActionCode, muse::Ret> AgentActionExecutor::actionFailed() const
{
    return m_actionFailed;
}

void AgentActionExecutor::onPreDispatch(const ActionCode& code)
{
    LOGD() << "AgentActionExecutor: Action starting: " << code;
}

void AgentActionExecutor::onPostDispatch(const ActionCode& code)
{
    LOGD() << "AgentActionExecutor: Action completed: " << code;
    m_actionCompleted.send(code);
}

