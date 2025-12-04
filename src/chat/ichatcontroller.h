/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "modularity/imoduleinterface.h"
#include "global/async/channel.h"
#include "global/types/ret.h"
#include "chattypes.h"

namespace au::chat {

class IChatController : MODULE_EXPORT_INTERFACE
{
    INTERFACE_ID(IChatController)

public:
    virtual ~IChatController() = default;

    virtual void init() = 0;
    virtual void deinit() = 0;

    // Send user message
    virtual muse::Ret sendMessage(const std::string& message) = 0;

    // Get chat messages
    virtual ChatMessageList messages() const = 0;

    // Approve or reject pending operation
    virtual muse::Ret approveOperation(const std::string& approvalId, bool approved, bool batchMode = false) = 0;

    // Cancel pending operation
    virtual muse::Ret cancelPendingOperation() = 0;

    // Notifications
    virtual muse::async::Channel<ChatMessage> messageReceived() const = 0;
    virtual muse::async::Channel<ApprovalRequest> approvalRequested() const = 0;
    virtual muse::async::Channel<> chatCleared() const = 0;
};

}

