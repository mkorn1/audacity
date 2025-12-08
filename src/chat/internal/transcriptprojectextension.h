/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "libraries/lib-project-file-io/ProjectFileIOExtension.h"

class AudacityProject;
class ProjectSerializer;
class ProjectFileIO;

namespace au::chat {
class TranscriptProjectExtension : public ProjectFileIOExtension
{
public:
    TranscriptProjectExtension();
    ~TranscriptProjectExtension() override = default;

    OnOpenAction OnOpen(AudacityProject& project, const std::string& path) override;
    void OnLoad(AudacityProject& project) override;
    OnSaveAction OnSave(AudacityProject& project, const ProjectSaveCallback& projectSaveCallback) override;
    OnCloseAction OnClose(AudacityProject& project) override;
    void OnUpdateSaved(AudacityProject& project, const ProjectSerializer& serializer) override;
    bool IsBlockLocked(const AudacityProject& project, int64_t blockId) const override;

private:
    void ensureTranscriptTable(AudacityProject& project);
    void saveTranscript(AudacityProject& project);
    void loadTranscript(AudacityProject& project);
};
}

