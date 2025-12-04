/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "iagentstatereader.h"
#include "modularity/ioc.h"
#include "async/asyncable.h"
#include "trackedit/iselectioncontroller.h"
#include "trackedit/itrackeditproject.h"
#include "context/iglobalcontext.h"

namespace au::chat {

class AgentStateReader : public IAgentStateReader, public muse::async::Asyncable
{
    muse::Inject<au::trackedit::ISelectionController> selectionController;
    muse::Inject<au::context::IGlobalContext> globalContext;

public:
    AgentStateReader();
    ~AgentStateReader() override;

    void init();

    // Selection state
    trackedit::TrackIdList selectedTracks() const override;
    trackedit::ClipKeyList selectedClips() const override;
    trackedit::secs_t selectionStartTime() const override;
    trackedit::secs_t selectionEndTime() const override;
    bool hasSelection() const override;

    // Project state
    trackedit::TrackList trackList() const override;
    trackedit::TrackIdList trackIdList() const override;
    trackedit::secs_t totalTime() const override;
    std::optional<trackedit::Track> track(trackedit::TrackId trackId) const override;

    // Clip queries
    trackedit::ClipKeyList clipsOnTrack(trackedit::TrackId trackId) const override;
    trackedit::Clip clip(const trackedit::ClipKey& key) const override;

    // Notifications
    muse::async::Channel<> stateChanged() const override;

private:
    au::trackedit::ITrackeditProjectPtr project() const;

    muse::async::Channel<> m_stateChanged;
};

}

