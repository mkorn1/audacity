/*
* Audacity: A Digital Audio Editor
*/
#include "chatcontroller.h"

#include "global/log.h"
#include "global/types/ret.h"

using namespace au::chat;
using namespace muse;

ChatController::ChatController()
{
}

ChatController::~ChatController()
{
}

void ChatController::init()
{
    // Create PythonBridge instance
    m_pythonBridge = std::make_shared<PythonBridgeImpl>();
    
    m_pythonBridge->messageReceived().onReceive(this, [this](const std::string& msg) {
        onPythonMessage(msg);
    });

    m_pythonBridge->approvalRequested().onReceive(this, [this](const ApprovalRequest& req) {
        onPythonApprovalRequest(req);
    });

    m_pythonBridge->errorOccurred().onReceive(this, [this](const std::string& err) {
        onPythonError(err);
    });

    m_pythonBridge->init();
}

void ChatController::deinit()
{
    if (m_pythonBridge) {
        m_pythonBridge->deinit();
    }
}

muse::Ret ChatController::sendMessage(const std::string& message)
{
    if (message.empty()) {
        return muse::make_ret(muse::Ret::Code::Ok);
    }

    // Add user message to list
    ChatMessage userMsg;
    userMsg.role = MessageRole::User;
    userMsg.content = message;
    // TODO: Add timestamp
    m_messages.push_back(userMsg);
    m_messageReceived.send(userMsg);

    // Send to Python service
    if (m_pythonBridge) {
        return m_pythonBridge->sendRequest(message);
    }
    return make_ret(Ret::Code::InternalError, std::string("PythonBridge not initialized"));
}

ChatMessageList ChatController::messages() const
{
    return m_messages;
}

muse::Ret ChatController::approveOperation(const std::string& approvalId, bool approved, bool batchMode)
{
    // For step-by-step approvals, the ID might have step suffix
    // Check if it matches base ID or exact match
    bool matches = (m_pendingApprovalId == approvalId) || 
                   (approvalId.find(m_pendingApprovalId) == 0);
    
    if (!matches && !m_pendingApprovalId.empty()) {
        // Try to match base ID (for step-by-step)
        std::string baseId = approvalId;
        size_t stepPos = baseId.find("_step_");
        if (stepPos != std::string::npos) {
            baseId = baseId.substr(0, stepPos);
        }
        matches = (m_pendingApprovalId == baseId);
    }
    
    if (!matches) {
        return make_ret(Ret::Code::InternalError, std::string("Invalid approval ID"));
    }

    // Use batch mode parameter
    if (m_pythonBridge) {
        return m_pythonBridge->sendApproval(approvalId, approved, batchMode);
    }
    return make_ret(Ret::Code::InternalError, std::string("PythonBridge not initialized"));
}

muse::Ret ChatController::cancelPendingOperation()
{
    if (m_pendingApprovalId.empty()) {
        return muse::make_ret(muse::Ret::Code::Ok);
    }

    std::string id = m_pendingApprovalId;
    m_pendingApprovalId.clear();
    if (m_pythonBridge) {
        return m_pythonBridge->sendApproval(id, false);
    }
    return make_ret(Ret::Code::InternalError, std::string("PythonBridge not initialized"));
}

muse::async::Channel<ChatMessage> ChatController::messageReceived() const
{
    return m_messageReceived;
}

muse::async::Channel<ApprovalRequest> ChatController::approvalRequested() const
{
    return m_approvalRequested;
}

muse::async::Channel<> ChatController::chatCleared() const
{
    return m_chatCleared;
}

void ChatController::onPythonMessage(const std::string& message)
{
    ChatMessage assistantMsg;
    assistantMsg.role = MessageRole::Assistant;
    
    // Parse message for canUndo flag
    std::string content = message;
    bool canUndo = false;
    
    size_t flagPos = content.find("|canUndo:true");
    if (flagPos != std::string::npos) {
        canUndo = true;
        content = content.substr(0, flagPos); // Remove flag from content
    }
    
    assistantMsg.content = content;
    assistantMsg.canUndo = canUndo;
    // TODO: Add timestamp
    m_messages.push_back(assistantMsg);
    m_messageReceived.send(assistantMsg);
}

void ChatController::onPythonApprovalRequest(const ApprovalRequest& request)
{
    m_pendingApprovalId = request.id;
    m_approvalRequested.send(request);
}

void ChatController::onPythonError(const std::string& error)
{
    ChatMessage errorMsg;
    errorMsg.role = MessageRole::System;
    errorMsg.content = "Error: " + error;
    m_messages.push_back(errorMsg);
    m_messageReceived.send(errorMsg);
}

