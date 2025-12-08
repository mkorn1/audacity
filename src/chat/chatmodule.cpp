/*
* Audacity: A Digital Audio Editor
*/
#include "chatmodule.h"

#include <QtQml>

#include "modularity/ioc.h"
#include "log.h"

#include "internal/chatcontroller.h"
#include "internal/agentactionexecutor.h"
#include "internal/agentstatereader.h"
#include "internal/agentfeedbackprovider.h"
#include "internal/transcriptservice.h"
#include "internal/transcriptprojectextension.h"
#include "view/chatviewmodel.h"

#include "libraries/lib-project-file-io/ProjectFileIOExtension.h"

#include "ui/iuiactionsregister.h"
#include "ui/iinteractiveuriregister.h"
#include "ui/iuiengine.h"

using namespace au::chat;
using namespace muse;
using namespace muse::modularity;
using namespace muse::ui;

static void chat_init_qrc()
{
    Q_INIT_RESOURCE(chat);
}

ChatModule::ChatModule()
    : m_chatController(std::make_shared<ChatController>()),
      m_chatViewModel(std::make_shared<ChatViewModel>()),
      m_transcriptService(std::make_shared<TranscriptService>()),
      m_transcriptProjectExtension(std::make_unique<TranscriptProjectExtension>())
{
    // Construct these in body to avoid multiple inheritance issues with make_shared
    m_actionExecutor = std::shared_ptr<AgentActionExecutor>(new AgentActionExecutor());
    m_stateReader = std::shared_ptr<AgentStateReader>(new AgentStateReader());
    m_feedbackProvider = std::shared_ptr<AgentFeedbackProvider>(new AgentFeedbackProvider());
    
    // Register the project file extension
    ProjectFileIOExtensionRegistry::Extension extension { *m_transcriptProjectExtension };
    UNUSED(extension); // Extension is registered via constructor
}

std::string ChatModule::moduleName() const
{
    return "chat";
}

void ChatModule::registerExports()
{
    ioc()->registerExport<IChatController>(moduleName(), m_chatController);
    ioc()->registerExport<IAgentActionExecutor>(moduleName(), m_actionExecutor);
    ioc()->registerExport<IAgentStateReader>(moduleName(), m_stateReader);
    ioc()->registerExport<IAgentFeedbackProvider>(moduleName(), m_feedbackProvider);
    ioc()->registerExport<ITranscriptService>(moduleName(), m_transcriptService);
    // PythonBridge will be created in chatcontroller
}

void ChatModule::registerUiTypes()
{
    qmlRegisterType<ChatViewModel>("Audacity.Chat", 1, 0, "ChatViewModel");
    
    // Register QML import path so QML files can be found
    // Note: IUiEngine is registered under "ui" module name
    auto uiEngine = ioc()->resolve<muse::ui::IUiEngine>("ui");
    if (uiEngine) {
        uiEngine->addSourceImportPath(QString::fromStdString(chat_QML_IMPORT));
    }
}

void ChatModule::resolveImports()
{
    auto ir = ioc()->resolve<muse::ui::IInteractiveUriRegister>(moduleName());
    if (ir) {
        // Register chat-related dialogs if needed
    }
}

void ChatModule::registerResources()
{
    chat_init_qrc();
}

void ChatModule::onInit(const muse::IApplication::RunMode&)
{
    m_chatController->init();
    m_actionExecutor->init();
    m_stateReader->init();
    m_feedbackProvider->init();
}

void ChatModule::onDeinit()
{
    m_chatController->deinit();
    m_actionExecutor->deinit();
}

