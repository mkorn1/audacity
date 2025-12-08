/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "modularity/imodulesetup.h"

namespace au::chat {
class ChatController;
class AgentActionExecutor;
class AgentStateReader;
class AgentFeedbackProvider;
class ChatViewModel;
class TranscriptService;
class TranscriptProjectExtension;

class ChatModule : public muse::modularity::IModuleSetup
{
public:
    ChatModule();

    std::string moduleName() const override;
    void registerExports() override;
    void registerResources() override;
    void registerUiTypes() override;
    void resolveImports() override;
    void onInit(const muse::IApplication::RunMode& mode) override;
    void onDeinit() override;

private:
    std::shared_ptr<ChatController> m_chatController;
    std::shared_ptr<AgentActionExecutor> m_actionExecutor;
    std::shared_ptr<AgentStateReader> m_stateReader;
    std::shared_ptr<AgentFeedbackProvider> m_feedbackProvider;
    std::shared_ptr<ChatViewModel> m_chatViewModel;
    std::shared_ptr<TranscriptService> m_transcriptService;
    std::unique_ptr<TranscriptProjectExtension> m_transcriptProjectExtension;
};
}

