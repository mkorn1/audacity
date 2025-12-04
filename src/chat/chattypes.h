/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include <string>
#include <vector>
#include <memory>

namespace au::chat {

enum class MessageRole {
    User,
    Assistant,
    System
};

struct ChatMessage {
    MessageRole role = MessageRole::User;
    std::string content;
    std::string timestamp;
    bool isPending = false;
    bool requiresApproval = false;
    std::string approvalId; // ID for approval workflow
    bool canUndo = false; // Whether this message represents an operation that can be undone
};

using ChatMessageList = std::vector<ChatMessage>;

struct ApprovalRequest {
    std::string id;
    std::string description;
    std::string preview; // Preview description or data
    std::vector<std::string> affectedItems; // What will be affected
    int currentStep = 0; // Current step for step-by-step approvals
    int totalSteps = 1; // Total number of steps
    std::string approvalMode = "batch"; // "batch" or "step_by_step"
};

struct ToolCall {
    std::string toolName;
    std::string actionCode;
    std::string parameters; // JSON string
    bool requiresApproval = false;
};

using ToolCallList = std::vector<ToolCall>;

}

