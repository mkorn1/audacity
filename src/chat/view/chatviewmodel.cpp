/*
* Audacity: A Digital Audio Editor
*/
#include "chatviewmodel.h"

#include "global/log.h"

using namespace au::chat;

ChatViewModel::ChatViewModel(QObject* parent)
    : QAbstractListModel(parent)
{
    if (chatController()) {
        chatController()->messageReceived().onReceive(this, [this](const ChatMessage& msg) {
            onMessageReceived(msg);
        });

        chatController()->approvalRequested().onReceive(this, [this](const ApprovalRequest& req) {
            onApprovalRequested(req);
        });

        // Load existing messages
        m_messages = chatController()->messages();
    }
}

QHash<int, QByteArray> ChatViewModel::roleNames() const
{
    QHash<int, QByteArray> roles;
    roles[RoleContent] = "content";
    roles[RoleRole] = "role";
    roles[RoleTimestamp] = "timestamp";
    roles[RoleIsPending] = "isPending";
    roles[RoleRequiresApproval] = "requiresApproval";
    roles[RoleCanUndo] = "canUndo";
    return roles;
}

int ChatViewModel::rowCount(const QModelIndex&) const
{
    return static_cast<int>(m_messages.size());
}

QVariant ChatViewModel::data(const QModelIndex& index, int role) const
{
    if (!index.isValid() || index.row() >= static_cast<int>(m_messages.size())) {
        return QVariant();
    }

    const ChatMessage& msg = m_messages[index.row()];

    switch (role) {
    case RoleContent:
        return QString::fromStdString(msg.content);
    case RoleRole:
        return static_cast<int>(msg.role);
    case RoleTimestamp:
        return QString::fromStdString(msg.timestamp);
    case RoleIsPending:
        return msg.isPending;
    case RoleRequiresApproval:
        return msg.requiresApproval;
    case RoleCanUndo:
        return msg.canUndo;
    default:
        return QVariant();
    }
}

void ChatViewModel::sendMessage(const QString& message)
{
    if (!chatController()) {
        return;
    }

    m_isProcessing = true;
    emit isProcessingChanged();

    muse::Ret ret = chatController()->sendMessage(message.toStdString());
    if (!ret) {
        LOGW() << "Failed to send message: " << ret.text();
        m_isProcessing = false;
        emit isProcessingChanged();
    }
}

void ChatViewModel::approveOperation(bool approved, bool batchMode)
{
    if (!chatController() || m_pendingApprovalId.empty()) {
        return;
    }

    std::string approvalId = m_pendingApprovalId;
    
    // Pass batch mode to controller
    muse::Ret ret = chatController()->approveOperation(approvalId, approved, batchMode);
    if (ret) {
        // Only clear if not step-by-step or if rejected
        if (!approved || batchMode || m_approvalStepTotal <= 1) {
            m_pendingApprovalId.clear();
            m_approvalDescription.clear();
            m_approvalPreview.clear();
            m_approvalStepCurrent = 0;
            m_approvalStepTotal = 1;
            emit hasPendingApprovalChanged();
            emit approvalChanged();
        }
    }
}

void ChatViewModel::cancelApproval()
{
    if (!chatController()) {
        return;
    }

    chatController()->cancelPendingOperation();
    m_pendingApprovalId.clear();
    m_approvalDescription.clear();
    m_approvalPreview.clear();
    m_approvalStepCurrent = 0;
    m_approvalStepTotal = 1;
    emit hasPendingApprovalChanged();
    emit approvalChanged();
}

void ChatViewModel::undo()
{
    if (!dispatcher()) {
        return;
    }

    // Dispatch undo action - use action://undo which routes to trackedit/undo
    dispatcher()->dispatch("action://undo");
}

void ChatViewModel::onMessageReceived(const ChatMessage& message)
{
    beginInsertRows(QModelIndex(), static_cast<int>(m_messages.size()), static_cast<int>(m_messages.size()));
    m_messages.push_back(message);
    endInsertRows();

    if (message.role == MessageRole::Assistant && !message.isPending) {
        m_isProcessing = false;
        emit isProcessingChanged();
    }
}

void ChatViewModel::onApprovalRequested(const ApprovalRequest& request)
{
    m_pendingApprovalId = request.id;
    m_approvalDescription = QString::fromStdString(request.description);
    m_approvalPreview = QString::fromStdString(request.preview);
    m_approvalStepCurrent = request.currentStep;
    m_approvalStepTotal = request.totalSteps;
    emit hasPendingApprovalChanged();
    emit approvalChanged();
}

