/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include <QAbstractListModel>
#include <QObject>

#include "modularity/ioc.h"
#include "async/asyncable.h"
#include "ichatcontroller.h"
#include "chattypes.h"
#include "actions/iactionsdispatcher.h"

namespace au::chat {

class ChatViewModel : public QAbstractListModel, public muse::async::Asyncable
{
    Q_OBJECT
    Q_PROPERTY(bool isProcessing READ isProcessing NOTIFY isProcessingChanged)
    Q_PROPERTY(bool hasPendingApproval READ hasPendingApproval NOTIFY hasPendingApprovalChanged)
    Q_PROPERTY(QString approvalDescription READ approvalDescription NOTIFY approvalChanged)
    Q_PROPERTY(QString approvalPreview READ approvalPreview NOTIFY approvalChanged)
    Q_PROPERTY(int approvalStepCurrent READ approvalStepCurrent NOTIFY approvalChanged)
    Q_PROPERTY(int approvalStepTotal READ approvalStepTotal NOTIFY approvalChanged)

    muse::Inject<IChatController> chatController;
    muse::Inject<muse::actions::IActionsDispatcher> dispatcher;

public:
    explicit ChatViewModel(QObject* parent = nullptr);

    enum Roles {
        RoleContent = Qt::UserRole + 1,
        RoleRole,
        RoleTimestamp,
        RoleIsPending,
        RoleRequiresApproval,
        RoleCanUndo
    };

    QHash<int, QByteArray> roleNames() const override;
    int rowCount(const QModelIndex& parent = QModelIndex()) const override;
    QVariant data(const QModelIndex& index, int role = Qt::DisplayRole) const override;

    Q_INVOKABLE void sendMessage(const QString& message);
    Q_INVOKABLE void approveOperation(bool approved, bool batchMode = false);
    Q_INVOKABLE void cancelApproval();
    Q_INVOKABLE void undo();

    bool isProcessing() const { return m_isProcessing; }
    bool hasPendingApproval() const { return !m_pendingApprovalId.empty(); }
    QString approvalDescription() const { return m_approvalDescription; }
    QString approvalPreview() const { return m_approvalPreview; }
    int approvalStepCurrent() const { return m_approvalStepCurrent; }
    int approvalStepTotal() const { return m_approvalStepTotal; }

    ChatMessageList messages() const { return m_messages; }

signals:
    void isProcessingChanged();
    void hasPendingApprovalChanged();
    void approvalChanged();

private:
    void onMessageReceived(const ChatMessage& message);
    void onApprovalRequested(const ApprovalRequest& request);

    ChatMessageList m_messages;
    bool m_isProcessing = false;
    std::string m_pendingApprovalId;
    QString m_approvalDescription;
    QString m_approvalPreview;
    int m_approvalStepCurrent = 0;
    int m_approvalStepTotal = 1;
};

}

