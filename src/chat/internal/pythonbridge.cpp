/*
* Audacity: A Digital Audio Editor
*/
#include "pythonbridge_impl.h"

#include "global/log.h"
#include "global/types/ret.h"
#include "actions/actiontypes.h"

#include <QProcess>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QDir>
#include <QFile>
#include <QStandardPaths>
#include <QCoreApplication>
#include <QString>

using namespace au::chat;
using namespace muse;

PythonBridgeImpl::PythonBridgeImpl()
    : m_pythonProcess(nullptr)
{
}

PythonBridgeImpl::~PythonBridgeImpl()
{
    deinit();
}

void PythonBridgeImpl::init()
{
    if (m_pythonProcess) {
        LOGW() << "PythonBridge: Already initialized";
        return;
    }

    // Find Python executable
    QString pythonExe = "python3";
    #ifdef Q_OS_WIN
    pythonExe = "python";
    #endif

    // Find the Python script path
    QString appDir = QCoreApplication::applicationDirPath();
    LOGI() << "PythonBridge: App directory: " << appDir;
    LOGI() << "PythonBridge: Current working directory: " << QDir::currentPath();

    QString scriptPath = appDir + "/../share/chat/agent_service.py";
    LOGI() << "PythonBridge: Trying path 1: " << scriptPath << " exists: " << QFile::exists(scriptPath);

    // Try alternative paths
    if (!QFile::exists(scriptPath)) {
        scriptPath = QDir::currentPath() + "/src/chat/python/agent_service.py";
        LOGI() << "PythonBridge: Trying path 2: " << scriptPath << " exists: " << QFile::exists(scriptPath);
    }
    if (!QFile::exists(scriptPath)) {
        scriptPath = "src/chat/python/agent_service.py";
        LOGI() << "PythonBridge: Trying path 3: " << scriptPath << " exists: " << QFile::exists(scriptPath);
    }
    // Try source directory relative to app bundle on macOS
    if (!QFile::exists(scriptPath)) {
        scriptPath = appDir + "/../../../../src/chat/python/agent_service.py";
        LOGI() << "PythonBridge: Trying path 4 (macOS bundle): " << scriptPath << " exists: " << QFile::exists(scriptPath);
    }

    if (!QFile::exists(scriptPath)) {
        LOGE() << "PythonBridge: Cannot find agent_service.py at any path";
        m_errorOccurred.send("Cannot find Python agent service script");
        return;
    }

    LOGI() << "PythonBridge: Using script path: " << scriptPath;
    m_pythonScriptPath = scriptPath;

    // Create and configure QProcess
    m_pythonProcess = new QProcess(this);
    m_pythonProcess->setProgram(pythonExe);
    m_pythonProcess->setArguments({ scriptPath });
    m_pythonProcess->setProcessChannelMode(QProcess::SeparateChannels); // Keep stderr separate from stdout

    // Connect signals
    connect(m_pythonProcess, &QProcess::readyReadStandardOutput, this, &PythonBridgeImpl::onProcessReadyRead);
    connect(m_pythonProcess, &QProcess::readyReadStandardError, this, &PythonBridgeImpl::onProcessStderrReady);
    connect(m_pythonProcess, &QProcess::errorOccurred, this, &PythonBridgeImpl::onProcessError);
    connect(m_pythonProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, &PythonBridgeImpl::onProcessFinished);

    // Start the process
    m_pythonProcess->start();
    
    if (!m_pythonProcess->waitForStarted(5000)) {
        LOGE() << "PythonBridge: Failed to start Python process";
        m_errorOccurred.send("Failed to start Python agent service");
        delete m_pythonProcess;
        m_pythonProcess = nullptr;
        return;
    }

    LOGI() << "PythonBridge: Started Python process (PID: " << m_pythonProcess->processId() << ")";
}

void PythonBridgeImpl::deinit()
{
    if (!m_pythonProcess) {
        return;
    }

    LOGI() << "PythonBridge: Stopping Python process";

    // Disconnect signals
    if (m_pythonProcess) {
        m_pythonProcess->disconnect();
    }

    // Terminate gracefully
    if (m_pythonProcess->state() == QProcess::Running) {
        m_pythonProcess->terminate();
        if (!m_pythonProcess->waitForFinished(3000)) {
            LOGW() << "PythonBridge: Process did not terminate, killing";
            m_pythonProcess->kill();
            m_pythonProcess->waitForFinished(1000);
        }
    }

    delete m_pythonProcess;
    m_pythonProcess = nullptr;
    m_stdoutBuffer.clear();

    LOGI() << "PythonBridge: Deinitialized";
}

muse::Ret PythonBridgeImpl::sendRequest(const std::string& message)
{
    if (!m_pythonProcess || m_pythonProcess->state() != QProcess::Running) {
        LOGE() << "PythonBridge: Process not running, cannot send request";
        return make_ret(Ret::Code::InternalError, std::string("Python process not running"));
    }

    // Create JSON request
    QJsonObject request;
    request["type"] = "message";
    request["message"] = QString::fromStdString(message);

    QJsonDocument doc(request);
    QByteArray jsonData = doc.toJson(QJsonDocument::Compact);
    jsonData.append('\n'); // Newline for Python to read line-by-line

    // Write to process stdin
    qint64 written = m_pythonProcess->write(jsonData);
    if (written != jsonData.size()) {
        LOGE() << "PythonBridge: Failed to write full request";
        return make_ret(Ret::Code::InternalError, std::string("Failed to write to Python process"));
    }

    // QProcess doesn't have flush - data is sent immediately
    LOGI() << "PythonBridge: Sent request: " << message;
    return muse::make_ret(muse::Ret::Code::Ok);
}

muse::Ret PythonBridgeImpl::sendApproval(const std::string& approvalId, bool approved, bool batchMode)
{
    if (!m_pythonProcess || m_pythonProcess->state() != QProcess::Running) {
        LOGE() << "PythonBridge: Process not running, cannot send approval";
        return make_ret(Ret::Code::InternalError, std::string("Python process not running"));
    }

    // Create JSON request
    QJsonObject request;
    request["type"] = "approval";
    request["approval_id"] = QString::fromStdString(approvalId);
    request["approved"] = approved;
    request["batch_mode"] = batchMode;

    QJsonDocument doc(request);
    QByteArray jsonData = doc.toJson(QJsonDocument::Compact);
    jsonData.append('\n'); // Newline for Python to read line-by-line

    // Write to process stdin
    qint64 written = m_pythonProcess->write(jsonData);
    if (written != jsonData.size()) {
        LOGE() << "PythonBridge: Failed to write full approval";
        return make_ret(Ret::Code::InternalError, std::string("Failed to write to Python process"));
    }

    // QProcess doesn't have flush - data is sent immediately
    LOGI() << "PythonBridge: Sent approval: " << approvalId << " = " << approved;
    return muse::make_ret(muse::Ret::Code::Ok);
}

void PythonBridgeImpl::onProcessReadyRead()
{
    if (!m_pythonProcess) {
        return;
    }

    QByteArray newData = m_pythonProcess->readAllStandardOutput();
    LOGI() << "PythonBridge: Received " << newData.size() << " bytes from Python";
    LOGI() << "PythonBridge: Raw data: " << newData.left(500).constData();
    m_stdoutBuffer.append(newData);

    // Process complete lines (JSON responses are line-delimited)
    int newlinePos;
    while ((newlinePos = m_stdoutBuffer.indexOf('\n')) >= 0) {
        QByteArray line = m_stdoutBuffer.left(newlinePos);
        m_stdoutBuffer.remove(0, newlinePos + 1);

        if (!line.isEmpty()) {
            LOGI() << "PythonBridge: Parsing line: " << line.left(200).constData();
            parseResponse(line);
        }
    }
}

void PythonBridgeImpl::onProcessStderrReady()
{
    if (!m_pythonProcess) {
        return;
    }

    QByteArray stderrData = m_pythonProcess->readAllStandardError();
    if (!stderrData.isEmpty()) {
        LOGD() << "PythonBridge (stderr): " << stderrData.constData();
    }
}

void PythonBridgeImpl::onProcessError(QProcess::ProcessError error)
{
    QString errorMsg;
    switch (error) {
    case QProcess::FailedToStart:
        errorMsg = "Python process failed to start";
        break;
    case QProcess::Crashed:
        errorMsg = "Python process crashed";
        break;
    case QProcess::Timedout:
        errorMsg = "Python process timed out";
        break;
    case QProcess::WriteError:
        errorMsg = "Error writing to Python process";
        break;
    case QProcess::ReadError:
        errorMsg = "Error reading from Python process";
        break;
    default:
        errorMsg = "Unknown Python process error";
        break;
    }

    LOGE() << "PythonBridge: " << errorMsg;
    m_errorOccurred.send(errorMsg.toStdString());
}

void PythonBridgeImpl::onProcessFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    if (exitStatus == QProcess::CrashExit) {
        LOGE() << "PythonBridge: Process crashed with exit code " << exitCode;
        m_errorOccurred.send("Python process crashed");
    } else if (exitCode != 0) {
        LOGW() << "PythonBridge: Process exited with code " << exitCode;
    } else {
        LOGI() << "PythonBridge: Process exited normally";
    }
}

void PythonBridgeImpl::parseResponse(const QByteArray& data)
{
    QJsonParseError error;
    QJsonDocument doc = QJsonDocument::fromJson(data, &error);

    if (error.error != QJsonParseError::NoError) {
        LOGE() << "PythonBridge: JSON parse error: " << error.errorString();
        m_errorOccurred.send("Invalid JSON response from Python service");
        return;
    }

    if (!doc.isObject()) {
        LOGE() << "PythonBridge: Response is not a JSON object";
        return;
    }

    QJsonObject response = doc.object();
    QString type = response["type"].toString();

    if (type == "message") {
        QString content = response["content"].toString();
        bool canUndo = response["can_undo"].toBool(false);
        
        // Send message with canUndo flag encoded in a special format
        // ChatController will parse this and set the canUndo flag
        // Format: "MESSAGE_CONTENT|canUndo:true" or just "MESSAGE_CONTENT"
        QString messageWithFlag = content;
        if (canUndo) {
            messageWithFlag += "|canUndo:true";
        }
        
        m_messageReceived.send(messageWithFlag.toStdString());
    } else if (type == "approval_request") {
        ApprovalRequest approval;
        approval.id = response["approval_id"].toString().toStdString();
        approval.description = response["description"].toString().toStdString();
        approval.preview = response["preview"].toString().toStdString();
        approval.currentStep = response["current_step"].toInt(0);
        approval.totalSteps = response["total_steps"].toInt(1);
        approval.approvalMode = response["approval_mode"].toString("batch").toStdString();
        m_approvalRequested.send(approval);
    } else if (type == "tool_call") {
        handleToolCall(response);
    } else if (type == "error") {
        QString content = response["content"].toString();
        m_errorOccurred.send(content.toStdString());
    } else {
        LOGW() << "PythonBridge: Unknown response type: " << type;
    }
}

muse::async::Channel<std::string> PythonBridgeImpl::messageReceived() const
{
    return m_messageReceived;
}

muse::async::Channel<ApprovalRequest> PythonBridgeImpl::approvalRequested() const
{
    return m_approvalRequested;
}

muse::async::Channel<std::string> PythonBridgeImpl::errorOccurred() const
{
    return m_errorOccurred;
}

muse::async::Channel<std::string> PythonBridgeImpl::toolResultReceived() const
{
    return m_toolResultReceived;
}

void PythonBridgeImpl::handleToolCall(const QJsonObject& request)
{
    QString callId = request["call_id"].toString();
    QString toolName = request["tool_name"].toString();
    QString actionCode = request["action_code"].toString();
    QJsonObject params = request["parameters"].toObject();

    LOGI() << "PythonBridge: Tool call - " << toolName << " (" << actionCode << ")";

    if (!actionExecutor()) {
        QJsonObject errorResult;
        errorResult["call_id"] = callId;
        errorResult["success"] = false;
        errorResult["error"] = "Action executor not available";
        sendToolResult(callId, errorResult);
        return;
    }

    // Convert JSON parameters to ActionData
    // For now, we'll pass empty ActionData - this can be extended later
    muse::actions::ActionData actionData;
    
    // Execute the action
    muse::Ret ret = actionExecutor()->executeAction(actionCode.toStdString(), actionData);

    // Build result
    QJsonObject result;
    result["call_id"] = callId;
    result["tool_name"] = toolName;
    result["action_code"] = actionCode;
    
    if (ret.valid()) {
        result["success"] = true;
        result["message"] = "Action executed successfully";
    } else {
        result["success"] = false;
        result["error"] = QString::fromStdString(ret.text());
    }

    sendToolResult(callId, result);
}

void PythonBridgeImpl::sendToolResult(const QString& callId, const QJsonObject& result)
{
    if (!m_pythonProcess || m_pythonProcess->state() != QProcess::Running) {
        LOGW() << "PythonBridge: Process not running, cannot send tool result";
        return;
    }

    // Send tool result as a request to Python (via stdin)
    QJsonObject request;
    request["type"] = "tool_result";
    request["result"] = result;

    QJsonDocument doc(request);
    QByteArray jsonData = doc.toJson(QJsonDocument::Compact);
    jsonData.append('\n');

    // Write to process stdin (Python reads requests from stdin)
    qint64 written = m_pythonProcess->write(jsonData);
    if (written != jsonData.size()) {
        LOGE() << "PythonBridge: Failed to write tool result";
        return;
    }

    LOGI() << "PythonBridge: Sent tool result for call_id: " << callId;
    
    // Also send to channel for any listeners
    QJsonDocument resultDoc(result);
    m_toolResultReceived.send(resultDoc.toJson(QJsonDocument::Compact).toStdString());
}

