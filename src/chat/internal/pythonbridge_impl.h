/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "pythonbridge.h"
#include "async/asyncable.h"
#include "modularity/ioc.h"
#include "iagentactionexecutor.h"
#include "iagentstatereader.h"
#include "actions/actiontypes.h"

#include <QObject>
#include <QProcess>

namespace au::chat {

class PythonBridgeImpl : public QObject, public PythonBridge, public muse::async::Asyncable
{
    Q_OBJECT
    
    muse::Inject<IAgentActionExecutor> actionExecutor;
    muse::Inject<IAgentStateReader> stateReader;
    
public:
    PythonBridgeImpl();
    ~PythonBridgeImpl() override;

    void init() override;
    void deinit() override;

    muse::Ret sendRequest(const std::string& message) override;
    muse::Ret sendApproval(const std::string& approvalId, bool approved, bool batchMode = false) override;

    muse::async::Channel<std::string> messageReceived() const override;
    muse::async::Channel<ApprovalRequest> approvalRequested() const override;
    muse::async::Channel<std::string> errorOccurred() const override;
    muse::async::Channel<std::string> toolResultReceived() const override;

private:
    void onProcessReadyRead();
    void onProcessError(QProcess::ProcessError error);
    void onProcessFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void parseResponse(const QByteArray& data);
    void handleToolCall(const QJsonObject& request);
    void sendToolResult(const QString& callId, const QJsonObject& result);
    
    QProcess* m_pythonProcess = nullptr;
    QString m_pythonScriptPath;
    QByteArray m_stdoutBuffer;
    
    muse::async::Channel<std::string> m_messageReceived;
    muse::async::Channel<ApprovalRequest> m_approvalRequested;
    muse::async::Channel<std::string> m_errorOccurred;
    muse::async::Channel<std::string> m_toolResultReceived;
};

}

