/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "ichatcontroller.h"
#include "pythonbridge.h"
#include "pythonbridge_impl.h"

#include "modularity/ioc.h"
#include "async/asyncable.h"

namespace au::chat {

class ChatController : public IChatController, public muse::async::Asyncable
{
    std::shared_ptr<PythonBridge> m_pythonBridge;

public:
    ChatController();
    ~ChatController() override;

    void init() override;
    void deinit() override;

    muse::Ret sendMessage(const std::string& message) override;
    ChatMessageList messages() const override;
    muse::Ret approveOperation(const std::string& approvalId, bool approved, bool batchMode = false) override;
    muse::Ret cancelPendingOperation() override;

    muse::async::Channel<ChatMessage> messageReceived() const override;
    muse::async::Channel<ApprovalRequest> approvalRequested() const override;
    muse::async::Channel<> chatCleared() const override;

private:
    void onPythonMessage(const std::string& message);
    void onPythonApprovalRequest(const ApprovalRequest& request);
    void onPythonError(const std::string& error);

    ChatMessageList m_messages;
    std::string m_pendingApprovalId;

    muse::async::Channel<ChatMessage> m_messageReceived;
    muse::async::Channel<ApprovalRequest> m_approvalRequested;
    muse::async::Channel<> m_chatCleared;
};

}

