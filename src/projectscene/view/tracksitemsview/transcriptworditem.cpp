/*
* Audacity: A Digital Audio Editor
*/
#include "transcriptworditem.h"
#include "projectscene/types/projectscenetypes.h"

using namespace au::projectscene;
using namespace au::trackedit;

TranscriptWordItem::TranscriptWordItem(QObject* parent)
    : ViewTrackItem(parent)
{
}

void TranscriptWordItem::setWord(const au::chat::TranscriptWord& word)
{
    setTitle(QString::fromStdString(word.word.toStdString()));
    m_isFiller = word.isFiller;
    m_confidence = word.confidence;

    // Create a unique key for this word (using start time as ID)
    // Note: This is a simple approach - in production you might want a more robust key
    trackedit::TrackItemKey trackeditKey;
    trackeditKey.trackId = -1; // Transcript doesn't belong to a track
    trackeditKey.itemId = static_cast<int64_t>(word.startTime * 1000); // Use milliseconds as ID
    m_key = TrackItemKey(trackeditKey);

    TrackItemTime time;
    time.startTime = word.startTime;
    time.endTime = word.endTime;
    time.itemStartTime = word.startTime;
    time.itemEndTime = word.endTime;
    setTime(time);

    emit isFillerChanged();
    emit confidenceChanged();
}

void TranscriptWordItem::setUtterance(const au::chat::TranscriptUtterance& utterance)
{
    setTitle(QString::fromStdString(utterance.text.toStdString()));
    m_isFiller = false; // Utterances aren't fillers
    m_confidence = 1.0; // Default confidence for utterances

    // Create a unique key for this utterance (using start time as ID)
    trackedit::TrackItemKey trackeditKey;
    trackeditKey.trackId = -1; // Transcript doesn't belong to a track
    trackeditKey.itemId = static_cast<int64_t>(utterance.startTime * 1000); // Use milliseconds as ID
    m_key = TrackItemKey(trackeditKey);

    TrackItemTime time;
    time.startTime = utterance.startTime;
    time.endTime = utterance.endTime;
    time.itemStartTime = utterance.startTime;
    time.itemEndTime = utterance.endTime;
    setTime(time);

    emit isFillerChanged();
    emit confidenceChanged();
}

bool TranscriptWordItem::isFiller() const
{
    return m_isFiller;
}

double TranscriptWordItem::confidence() const
{
    return m_confidence;
}

