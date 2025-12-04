/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "modularity/imoduleinterface.h"
#include "global/async/channel.h"
#include "global/types/ret.h"
#include "chattypes.h"

namespace au::chat {

class PythonBridge : MODULE_EXPORT_INTERFACE
{
    INTERFACE_ID(PythonBridge)

public:
    virtual ~PythonBridge() = default;

    virtual void init() = 0;
    virtual void deinit() = 0;

    // Send request to Python service
    virtual muse::Ret sendRequest(const std::string& message) = 0;

    // Send approval response
    virtual muse::Ret sendApproval(const std::string& approvalId, bool approved, bool batchMode = false) = 0;

    // Notifications from Python
    virtual muse::async::Channel<std::string> messageReceived() const = 0;
    virtual muse::async::Channel<ApprovalRequest> approvalRequested() const = 0;
    virtual muse::async::Channel<std::string> errorOccurred() const = 0;
    virtual muse::async::Channel<std::string> toolResultReceived() const = 0;
};

}

