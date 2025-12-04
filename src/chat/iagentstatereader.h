/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "modularity/imoduleinterface.h"
#include "global/async/channel.h"
#include "trackedit/trackedittypes.h"
#include "trackedit/dom/track.h"
#include "trackedit/dom/clip.h"

namespace au::chat {

class IAgentStateReader : MODULE_EXPORT_INTERFACE
{
    INTERFACE_ID(IAgentStateReader)

public:
    virtual ~IAgentStateReader() = default;

    // Selection state
    virtual trackedit::TrackIdList selectedTracks() const = 0;
    virtual trackedit::ClipKeyList selectedClips() const = 0;
    virtual trackedit::secs_t selectionStartTime() const = 0;
    virtual trackedit::secs_t selectionEndTime() const = 0;
    virtual bool hasSelection() const = 0;

    // Project state
    virtual trackedit::TrackList trackList() const = 0;
    virtual trackedit::TrackIdList trackIdList() const = 0;
    virtual trackedit::secs_t totalTime() const = 0;
    virtual std::optional<trackedit::Track> track(trackedit::TrackId trackId) const = 0;

    // Clip queries
    virtual trackedit::ClipKeyList clipsOnTrack(trackedit::TrackId trackId) const = 0;
    virtual trackedit::Clip clip(const trackedit::ClipKey& key) const = 0;

    // Notifications
    virtual muse::async::Channel<> stateChanged() const = 0;
};

}

