/*
* Audacity: A Digital Audio Editor
*/
#include "agentstatereader.h"

#include "global/log.h"
#include "trackedit/itrackeditproject.h"

using namespace au::chat;
using namespace au::trackedit;
using namespace muse;

AgentStateReader::AgentStateReader()
{
}

AgentStateReader::~AgentStateReader()
{
}

void AgentStateReader::init()
{
    // Subscribe to state changes
    selectionController()->tracksSelected().onReceive(this, [this](const TrackIdList&) {
        m_stateChanged.send();
    });

    selectionController()->clipsSelected().onReceive(this, [this](const ClipKeyList&) {
        m_stateChanged.send();
    });

    selectionController()->dataSelectedStartTimeChanged().onReceive(this, [this](secs_t) {
        m_stateChanged.send();
    });

    globalContext()->currentTrackeditProjectChanged().onNotify(this, [this]() {
        m_stateChanged.send();
    });
}

TrackIdList AgentStateReader::selectedTracks() const
{
    return selectionController()->selectedTracks();
}

ClipKeyList AgentStateReader::selectedClips() const
{
    return selectionController()->selectedClips();
}

secs_t AgentStateReader::selectionStartTime() const
{
    return selectionController()->dataSelectedStartTime();
}

secs_t AgentStateReader::selectionEndTime() const
{
    return selectionController()->dataSelectedEndTime();
}

bool AgentStateReader::hasSelection() const
{
    return selectionController()->timeSelectionIsNotEmpty() || selectionController()->hasSelectedClips();
}

au::trackedit::TrackList AgentStateReader::trackList() const
{
    auto prj = project();
    if (!prj) {
        return au::trackedit::TrackList();
    }
    return prj->trackList();
}

TrackIdList AgentStateReader::trackIdList() const
{
    auto prj = project();
    if (!prj) {
        return TrackIdList();
    }
    return prj->trackIdList();
}

secs_t AgentStateReader::totalTime() const
{
    auto prj = project();
    if (!prj) {
        return 0.0;
    }
    return prj->totalTime().to_double();
}

std::optional<Track> AgentStateReader::track(TrackId trackId) const
{
    auto prj = project();
    if (!prj) {
        return std::nullopt;
    }
    return prj->track(trackId);
}

ClipKeyList AgentStateReader::clipsOnTrack(TrackId trackId) const
{
    auto prj = project();
    if (!prj) {
        return ClipKeyList();
    }
    // Get clips from project
    auto clipList = prj->clipList(trackId);
    ClipKeyList keys;
    for (const auto& clip : clipList) {
        keys.push_back(clip.key);
    }
    return keys;
}

Clip AgentStateReader::clip(const ClipKey& key) const
{
    auto prj = project();
    if (!prj) {
        return Clip();
    }
    return prj->clip(key);
}

muse::async::Channel<> AgentStateReader::stateChanged() const
{
    return m_stateChanged;
}

ITrackeditProjectPtr AgentStateReader::project() const
{
    return globalContext()->currentTrackeditProject();
}

