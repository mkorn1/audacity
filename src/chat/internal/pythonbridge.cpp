/*
* Audacity: A Digital Audio Editor
*/
#include "pythonbridge_impl.h"
#include "transcriptjsonconverter.h"

#include "global/log.h"
#include "global/types/ret.h"
#include "actions/actiontypes.h"
#include "trackedit/trackedittypes.h"
#include "trackedit/dom/track.h"
#include "trackedit/dom/clip.h"

#include <QProcess>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QDir>
#include <QFile>
#include <QStandardPaths>
#include <QCoreApplication>
#include <QString>
#include <QTemporaryFile>

// For direct WaveTrack access
#include "au3wrap/au3types.h"
#include "libraries/lib-track/Track.h"
#include "libraries/lib-wave-track/WaveTrack.h"
#include "libraries/lib-project-rate/ProjectRate.h"
#include "libraries/lib-math/SampleFormat.h"
#include <sndfile.h>
#include <wx/file.h>
#include <vector>
#include <memory>
#include <algorithm>
#include <cstring>

using namespace au::chat;
using namespace muse;
using namespace au::au3;

namespace {
// Helper function to convert TrackType enum to string
std::string trackTypeToString(au::trackedit::TrackType type)
{
    switch (type) {
    case au::trackedit::TrackType::Undefined:
        return "Undefined";
    case au::trackedit::TrackType::Mono:
        return "Mono";
    case au::trackedit::TrackType::Stereo:
        return "Stereo";
    case au::trackedit::TrackType::Label:
        return "Label";
    }
    return "Unknown";
}

// Helper function to export audio directly from WaveTracks to WAV file
QString exportWaveTracksToWav(Au3Project* project, const QString& outputPath)
{
    if (!project) {
        LOGE() << "PythonBridge: No project available";
        return QString();
    }

    auto& tracks = TrackList::Get(*project);
    auto waveTracks = tracks.Any<const WaveTrack>();
    
    if (waveTracks.empty()) {
        LOGE() << "PythonBridge: No WaveTracks found in project";
        return QString();
    }

    // Get project sample rate
    double sampleRate = ProjectRate::Get(*project).GetRate();
    if (sampleRate <= 0) {
        // Fallback: use rate from first track
        sampleRate = (*waveTracks.begin())->GetRate();
    }

    // Calculate total duration
    double t0 = 0.0;
    double t1 = 0.0;
    for (const auto& track : waveTracks) {
        double trackStart = track->GetStartTime();
        double trackEnd = track->GetEndTime();
        if (trackStart < t0 || t0 == 0.0) {
            t0 = trackStart;
        }
        if (trackEnd > t1) {
            t1 = trackEnd;
        }
    }

    double duration = t1 - t0;
    if (duration <= 0) {
        LOGE() << "PythonBridge: Project has no audio duration";
        return QString();
    }

    LOGI() << "PythonBridge: Exporting " << waveTracks.size() << " tracks, duration: " << duration << "s, rate: " << sampleRate;

    // Setup libsndfile for WAV output
    SF_INFO sfinfo;
    memset(&sfinfo, 0, sizeof(sfinfo));
    sfinfo.samplerate = static_cast<int>(sampleRate);
    sfinfo.channels = 1; // Mono output for transcription
    sfinfo.format = SF_FORMAT_WAV | SF_FORMAT_PCM_16;

    wxFile f;
    wxString wxPath = wxString::FromUTF8(outputPath.toStdString().c_str());
    if (!f.Open(wxPath, wxFile::write)) {
        LOGE() << "PythonBridge: Failed to create output file: " << outputPath;
        return QString();
    }

    SNDFILE* sf = sf_open_fd(f.fd(), SFM_WRITE, &sfinfo, FALSE);
    if (!sf) {
        LOGE() << "PythonBridge: Failed to open sndfile: " << sf_strerror(nullptr);
        f.Close();
        return QString();
    }

    // Read and mix samples
    const size_t bufferSize = 65536; // 64k samples per buffer
    std::vector<float> mixedBuffer(bufferSize, 0.0f);
    std::vector<float> trackBuffer(bufferSize, 0.0f);
    std::vector<const float*> trackBuffers;
    
    sampleCount totalSamples = sampleCount(duration * sampleRate);
    sampleCount samplesProcessed = 0;
    size_t numTracks = 0;

    // Count tracks and prepare buffers
    for (const auto& track : waveTracks) {
        if (!track->GetMute()) { // Skip muted tracks
            trackBuffers.push_back(nullptr);
            numTracks++;
        }
    }

    if (numTracks == 0) {
        LOGE() << "PythonBridge: All tracks are muted";
        sf_close(sf);
        f.Close();
        return QString();
    }

    LOGI() << "PythonBridge: Mixing " << numTracks << " active tracks";

    // Process in chunks
    while (samplesProcessed < totalSamples) {
        size_t samplesToRead = std::min(bufferSize, (totalSamples - samplesProcessed).as_size_t());
        
        // Clear mixed buffer
        std::fill(mixedBuffer.begin(), mixedBuffer.begin() + samplesToRead, 0.0f);

        // Read from each track and mix
        double currentTime = t0 + (samplesProcessed.as_double() / sampleRate);
        
        for (const auto& track : waveTracks) {
            if (track->GetMute()) {
                continue; // Skip muted tracks
            }

            double trackStart = track->GetStartTime();
            double trackEnd = track->GetEndTime();
            
            // Check if this time range overlaps with the track
            double readStartTime = currentTime;
            double readEndTime = currentTime + (samplesToRead / sampleRate);
            
            if (readEndTime < trackStart || readStartTime > trackEnd) {
                continue; // No overlap, skip this track
            }
            
            // Calculate sample offset relative to track start
            // If track starts after t0, we need to account for that
            double relativeStartTime = std::max(0.0, readStartTime - trackStart);
            sampleCount trackStartSample = sampleCount(relativeStartTime * track->GetRate());
            
            // Adjust samplesToRead if we're near track boundaries
            size_t actualSamplesToRead = samplesToRead;
            if (readStartTime < trackStart) {
                // Track hasn't started yet, skip some samples
                size_t skipSamples = static_cast<size_t>((trackStart - readStartTime) * sampleRate);
                if (skipSamples >= samplesToRead) {
                    continue; // Entire chunk is before track starts
                }
                actualSamplesToRead = samplesToRead - skipSamples;
                trackStartSample = 0;
            } else if (readEndTime > trackEnd) {
                // Track ends before chunk ends
                actualSamplesToRead = static_cast<size_t>((trackEnd - readStartTime) * sampleRate);
                if (actualSamplesToRead == 0) {
                    continue;
                }
            }
            
            // Read samples from track (relative to track's start)
            // DoGet expects an array of samplePtr (char*), so we need to cast
            samplePtr trackBufferPtr = reinterpret_cast<samplePtr>(trackBuffer.data());
            const samplePtr buffers[] = { trackBufferPtr };
            bool success = track->DoGet(
                0, 1, buffers, floatSample,
                trackStartSample, actualSamplesToRead,
                false, // not backwards
                FillFormat::fillZero,
                false // mayThrow = false, return false on error
            );

            if (success) {
                // Mix into output buffer (simple sum)
                // Account for offset if track started after chunk start
                size_t bufferOffset = 0;
                if (readStartTime < trackStart) {
                    bufferOffset = static_cast<size_t>((trackStart - readStartTime) * sampleRate);
                }
                
                for (size_t i = 0; i < actualSamplesToRead && (bufferOffset + i) < samplesToRead; i++) {
                    mixedBuffer[bufferOffset + i] += trackBuffer[i] * track->GetVolume();
                }
            }
        }

        // Write mixed samples to file (convert float to int16)
        std::vector<short> int16Buffer(samplesToRead);
        for (size_t i = 0; i < samplesToRead; i++) {
            // Clamp to [-1.0, 1.0] and convert to int16
            float sample = std::max(-1.0f, std::min(1.0f, mixedBuffer[i]));
            int16Buffer[i] = static_cast<short>(sample * 32767.0f);
        }

        sf_count_t framesWritten = sf_writef_short(sf, int16Buffer.data(), samplesToRead);
        if (framesWritten != static_cast<sf_count_t>(samplesToRead)) {
            LOGE() << "PythonBridge: Failed to write all samples, wrote " << framesWritten << " of " << samplesToRead;
            break;
        }

        samplesProcessed += samplesToRead;
    }

    sf_close(sf);
    f.Close();

    LOGI() << "PythonBridge: Successfully exported " << samplesProcessed.as_long_long() << " samples to " << outputPath;
    return outputPath;
}
}

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
    LOGD() << "PythonBridge: Received " << newData.size() << " bytes from Python";
    m_stdoutBuffer.append(newData);

    // Process complete lines (JSON responses are line-delimited)
    int newlinePos;
    while ((newlinePos = m_stdoutBuffer.indexOf('\n')) >= 0) {
        QByteArray line = m_stdoutBuffer.left(newlinePos);
        m_stdoutBuffer.remove(0, newlinePos + 1);

        if (!line.isEmpty()) {
            LOGD() << "PythonBridge: Parsing line: " << line.left(200).constData();
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
    } else if (type == "state_query") {
        handleStateQuery(response);
    } else if (type == "error") {
        QString content = response["content"].toString();
        m_errorOccurred.send(content.toStdString());
    } else if (type == "clarification_needed") {
        // Handle clarification requests - send as a regular message to the user
        QString content = response["content"].toString();
        m_messageReceived.send(content.toStdString());
    } else if (type == "transcript_data") {
        // Handle transcript data from Python
        QJsonObject transcriptJson = response["transcript"].toObject();
        if (!transcriptJson.isEmpty() && transcriptService()) {
            Transcript transcript = TranscriptJsonConverter::fromJson(transcriptJson);
            transcriptService()->setTranscript(transcript);
            LOGI() << "PythonBridge: Received transcript with " << transcript.words.size() << " words";
        }
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

void PythonBridgeImpl::handleStateQuery(const QJsonObject& request)
{
    QString callId = request["call_id"].toString();
    QString queryType = request["query_type"].toString();
    QJsonObject params = request["parameters"].toObject();

    LOGD() << "PythonBridge: State query - " << queryType;

    if (!stateReader()) {
        QJsonObject errorResult;
        errorResult["call_id"] = callId;
        errorResult["success"] = false;
        errorResult["error"] = "State reader not available";
        sendToolResult(callId, errorResult);
        return;
    }

    QJsonObject result;
    result["call_id"] = callId;
    result["query_type"] = queryType;

    try {
        if (queryType == "get_selection_start_time") {
            double startTime = stateReader()->selectionStartTime();
            result["success"] = true;
            result["value"] = startTime;
        } else if (queryType == "get_selection_end_time") {
            double endTime = stateReader()->selectionEndTime();
            result["success"] = true;
            result["value"] = endTime;
        } else if (queryType == "has_time_selection") {
            bool hasSelection = stateReader()->hasSelection();
            result["success"] = true;
            result["value"] = hasSelection;
        } else if (queryType == "get_selected_tracks") {
            auto trackIds = stateReader()->selectedTracks();
            QJsonArray trackIdArray;
            for (const auto& trackId : trackIds) {
                trackIdArray.append(QString::number(trackId));
            }
            result["success"] = true;
            result["value"] = trackIdArray;
        } else if (queryType == "get_selected_clips") {
            auto clipKeys = stateReader()->selectedClips();
            QJsonArray clipKeyArray;
            for (const auto& clipKey : clipKeys) {
                QJsonObject clipKeyObj;
                clipKeyObj["track_id"] = QString::number(clipKey.trackId);
                clipKeyObj["clip_id"] = QString::number(clipKey.itemId);
                clipKeyArray.append(clipKeyObj);
            }
            result["success"] = true;
            result["value"] = clipKeyArray;
        } else if (queryType == "get_cursor_position") {
            // Get cursor position from playback state
            if (globalContext() && globalContext()->playbackState()) {
                double cursorPos = globalContext()->playbackState()->playbackPosition().to_double();
                result["success"] = true;
                result["value"] = cursorPos;
            } else {
                result["success"] = false;
                result["error"] = "Playback state not available";
            }
        } else if (queryType == "get_total_project_time") {
            double totalTime = stateReader()->totalTime();
            result["success"] = true;
            result["value"] = totalTime;
        } else if (queryType == "get_track_list") {
            auto tracks = stateReader()->trackList();
            QJsonArray trackArray;
            for (const auto& track : tracks) {
                QJsonObject trackObj;
                trackObj["track_id"] = QString::number(track.id);
                trackObj["name"] = QString::fromStdString(track.title.toStdString());
                trackObj["type"] = QString::fromStdString(trackTypeToString(track.type));
                trackArray.append(trackObj);
            }
            result["success"] = true;
            result["value"] = trackArray;
        } else if (queryType == "get_clips_on_track") {
            QString trackIdStr = params["track_id"].toString();
            if (trackIdStr.isEmpty()) {
                result["success"] = false;
                result["error"] = "track_id parameter required";
            } else {
                bool ok;
                int64_t trackIdValue = trackIdStr.toLongLong(&ok);
                if (!ok) {
                    result["success"] = false;
                    result["error"] = "Invalid track_id format";
                } else {
                    au::trackedit::TrackId trackId(trackIdValue);
                    auto clipKeys = stateReader()->clipsOnTrack(trackId);
                    QJsonArray clipKeyArray;
                    for (const auto& clipKey : clipKeys) {
                        QJsonObject clipKeyObj;
                        clipKeyObj["track_id"] = QString::number(clipKey.trackId);
                        clipKeyObj["clip_id"] = QString::number(clipKey.itemId);
                        clipKeyArray.append(clipKeyObj);
                    }
                    result["success"] = true;
                    result["value"] = clipKeyArray;
                }
            }
        } else if (queryType == "get_all_labels") {
            // TODO: Implement label track queries when label track support is added
            result["success"] = true;
            result["value"] = QJsonArray(); // Empty array for now
        } else if (queryType == "action_enabled") {
            QString actionCode = params["action_code"].toString();
            if (actionCode.isEmpty()) {
                result["success"] = false;
                result["error"] = "action_code parameter required";
            } else {
                bool enabled = false;
                if (actionExecutor()) {
                    enabled = actionExecutor()->isActionEnabled(actionCode.toStdString());
                }
                result["success"] = true;
                result["value"] = enabled;
            }
        } else if (queryType == "get_project_audio_path") {
            // Export project audio directly from WaveTracks to a temporary WAV file for transcription
            if (!globalContext() || !globalContext()->currentProject()) {
                result["success"] = false;
                result["error"] = "No project available";
            } else {
                // Set up temp directory and filename
                QString tempDir = QStandardPaths::writableLocation(QStandardPaths::TempLocation);
                QString filename = "audacity_transcription_export.wav";
                QString fullPath = tempDir + "/" + filename;

                // Get Au3Project pointer
                Au3Project* project = reinterpret_cast<Au3Project*>(
                    globalContext()->currentProject()->au3ProjectPtr()
                );

                // Export directly from WaveTracks
                QString exportedPath = exportWaveTracksToWav(project, fullPath);

                if (!exportedPath.isEmpty()) {
                    // Verify file exists and check size
                    QFile exportedFile(exportedPath);
                    if (exportedFile.exists()) {
                        qint64 fileSize = exportedFile.size();
                        if (fileSize > 44) {  // More than just WAV header
                            result["success"] = true;
                            result["value"] = exportedPath;
                            LOGI() << "PythonBridge: Direct export successful - " << exportedPath << " (" << fileSize << " bytes)";
                        } else {
                            result["success"] = false;
                            result["error"] = QString("Export file is too small (%1 bytes, expected audio data)").arg(fileSize);
                            LOGE() << "PythonBridge: Export file too small: " << exportedPath << " (" << fileSize << " bytes)";
                        }
                    } else {
                        result["success"] = false;
                        result["error"] = "Export completed but file not found";
                        LOGE() << "PythonBridge: Export file not found: " << exportedPath;
                    }
                } else {
                    result["success"] = false;
                    result["error"] = "Failed to export audio from WaveTracks";
                    LOGE() << "PythonBridge: Direct export failed";
                }
            }
        } else {
            result["success"] = false;
            result["error"] = QString("Unknown query type: %1").arg(queryType);
        }
    } catch (const std::exception& e) {
        result["success"] = false;
        result["error"] = QString("Exception: %1").arg(e.what());
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

    LOGD() << "PythonBridge: Sent tool result for call_id: " << callId;
    
    // Also send to channel for any listeners
    QJsonDocument resultDoc(result);
    m_toolResultReceived.send(resultDoc.toJson(QJsonDocument::Compact).toStdString());
}

