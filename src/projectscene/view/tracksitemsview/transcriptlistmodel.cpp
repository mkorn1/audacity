/*
* Audacity: A Digital Audio Editor
*/
#include "transcriptlistmodel.h"
#include "transcriptworditem.h"

#include "global/async/async.h"
#include "log.h"

using namespace au::projectscene;
using namespace au::chat;

TranscriptListModel::TranscriptListModel(QObject* parent)
    : TrackItemsListModel(parent)
{
    // Transcripts don't belong to a track, so set a dummy trackId (0) to pass the assertion
    // We won't actually use this trackId for anything - transcripts are project-level
    setTrackId(0);
}

void TranscriptListModel::onInit()
{
    if (!transcriptService()) {
        LOGW() << "TranscriptListModel: TranscriptService not available";
        return;
    }

    // Get initial transcript if available
    if (transcriptService()->hasTranscript()) {
        m_transcript = transcriptService()->transcript();
        LOGI() << "TranscriptListModel: Loaded initial transcript with " << m_transcript.words.size() << " words";
    }

    // Subscribe to transcript changes
    transcriptService()->transcriptChanged().onReceive(this, [this](const Transcript& transcript) {
        m_transcript = transcript;
        LOGI() << "TranscriptListModel: Transcript changed, " << transcript.words.size() << " words";
        updateZoomLevel();
        // Call onReload() directly to bypass project check in base class reload()
        if (m_context) {
            disconnectAutoScroll();
            onReload();
        }
    }, muse::async::Asyncable::Mode::SetReplace);

    transcriptService()->transcriptCleared().onNotify(this, [this]() {
        m_transcript = Transcript();
        // Call onReload() directly to bypass project check in base class reload()
        if (m_context) {
            disconnectAutoScroll();
            onReload();
        }
    }, muse::async::Asyncable::Mode::SetReplace);

    // Subscribe to context changes - when context becomes available, reload if we have a transcript
    connect(this, &TrackItemsListModel::timelineContextChanged, this, [this]() {
        if (m_context && m_transcript.isValid()) {
            LOGI() << "TranscriptListModel: Context became available, reloading transcript";
            disconnectAutoScroll();
            onReload();
        }
        // Connect to zoom/frameTime changes when context is set
        if (m_context) {
            connect(m_context, &TimelineContext::zoomChanged, this, &TranscriptListModel::updateZoomLevel);
            connect(m_context, &TimelineContext::frameTimeChanged, this, &TranscriptListModel::updateItemsMetrics);
        }
    });

    // If we have an initial transcript and context, load it immediately
    // (bypassing the base class reload() which requires a project)
    if (m_transcript.isValid() && m_context) {
        LOGI() << "TranscriptListModel: Calling onReload() directly for initial transcript";
        onReload();
    }
}

void TranscriptListModel::onReload()
{
    LOGI() << "TranscriptListModel::onReload() called, transcript valid: " << m_transcript.isValid() 
           << ", context: " << (m_context != nullptr)
           << ", transcriptService: " << (transcriptService() != nullptr);

    if (!transcriptService() || !m_transcript.isValid()) {
        // Clear items if no transcript
        if (!m_items.isEmpty()) {
            beginRemoveRows(QModelIndex(), 0, m_items.size() - 1);
            qDeleteAll(m_items);
            m_items.clear();
            endRemoveRows();
        }
        return;
    }

    if (!m_context) {
        LOGW() << "TranscriptListModel::onReload() - no context, cannot update";
        return;
    }

    update();
}

void TranscriptListModel::update()
{
    if (!m_context || !m_transcript.isValid()) {
        // Clear items if no transcript or context
        if (!m_items.isEmpty()) {
            beginRemoveRows(QModelIndex(), 0, m_items.size() - 1);
            qDeleteAll(m_items);
            m_items.clear();
            endRemoveRows();
        }
        return;
    }

    // Get visible time range
    double frameStartTime = m_context->frameStartTime();
    double frameEndTime = m_context->frameEndTime();
    const double cacheTime = cacheBufferPx() / m_context->zoom();

    // Expand range for caching
    double itemStartTime = std::max(0.0, frameStartTime - cacheTime);
    double itemEndTime = frameEndTime + cacheTime;

    LOGI() << "TranscriptListModel::update() - time range: " << itemStartTime << " to " << itemEndTime
           << ", total words: " << m_transcript.words.size();

    // Get items in range
    std::vector<TranscriptWord> words;
    std::vector<TranscriptUtterance> utterances;

    if (m_useUtteranceLevel) {
        utterances = transcriptService()->utterancesInRange(itemStartTime, itemEndTime);
        LOGI() << "TranscriptListModel::update() - found " << utterances.size() << " utterances in range";
    } else {
        words = transcriptService()->wordsInRange(itemStartTime, itemEndTime);
        LOGI() << "TranscriptListModel::update() - found " << words.size() << " words in range";
    }

    // Clear existing items
    if (!m_items.isEmpty()) {
        beginRemoveRows(QModelIndex(), 0, m_items.size() - 1);
        qDeleteAll(m_items);
        m_items.clear();
        endRemoveRows();
    }

    // Create new items
    QList<TranscriptWordItem*> newList;

    if (m_useUtteranceLevel) {
        for (const auto& utterance : utterances) {
            TranscriptWordItem* item = new TranscriptWordItem(this);
            item->setUtterance(utterance);
            newList.append(item);
        }
    } else {
        for (const auto& word : words) {
            TranscriptWordItem* item = new TranscriptWordItem(this);
            item->setWord(word);
            newList.append(item);
        }
    }

    // Add new items
    if (!newList.isEmpty()) {
        beginInsertRows(QModelIndex(), 0, newList.size() - 1);
        for (TranscriptWordItem* item : newList) {
            m_items.append(item);
            LOGI() << "TranscriptListModel::update() - adding item:" << item->title().toStdString()
                   << " time:" << item->time().startTime << "-" << item->time().endTime;
        }
        endInsertRows();
        LOGI() << "TranscriptListModel::update() - added " << newList.size() << " items to model, total rowCount will be:" << m_items.size();
    } else {
        LOGW() << "TranscriptListModel::update() - no items to add";
    }

    updateItemsMetrics();
    
    LOGI() << "TranscriptListModel::update() - completed, rowCount:" << rowCount(QModelIndex());
}

void TranscriptListModel::updateItemMetrics(ViewTrackItem* viewItem)
{
    TranscriptWordItem* item = static_cast<TranscriptWordItem*>(viewItem);

    if (!m_context) {
        LOGW() << "TranscriptListModel::updateItemMetrics - no context";
        return;
    }

    TrackItemTime time = item->time();
    const double cacheTime = cacheBufferPx() / m_context->zoom();

    // Store clamped values for caching/visibility optimization
    time.itemStartTime = std::max(time.startTime, (m_context->frameStartTime() - cacheTime));
    time.itemEndTime = std::min(time.endTime, (m_context->frameEndTime() + cacheTime));

    item->setTime(time);
    
    // Use actual timestamps for accurate positioning (not clamped values)
    double x = m_context->timeToPosition(time.startTime);
    double width = (time.endTime - time.startTime) * m_context->zoom();
    
    item->setX(x);
    item->setWidth(width);
    // Margins use actual timestamps for accurate clipping
    item->setLeftVisibleMargin(std::max(m_context->frameStartTime() - time.startTime, 0.0) * m_context->zoom());
    item->setRightVisibleMargin(std::max(time.endTime - m_context->frameEndTime(), 0.0) * m_context->zoom());

    LOGI() << "TranscriptListModel::updateItemMetrics - item:" << item->title().toStdString()
           << " time:" << time.startTime << "-" << time.endTime
           << " x:" << x << " width:" << width
           << " frame:" << m_context->frameStartTime() << "-" << m_context->frameEndTime()
           << " zoom:" << m_context->zoom();
}

au::trackedit::TrackItemKeyList TranscriptListModel::getSelectedItemKeys() const
{
    // Transcript items don't support selection yet
    return trackedit::TrackItemKeyList();
}

void TranscriptListModel::updateZoomLevel()
{
    if (!m_context) {
        return;
    }

    double visibleDuration = m_context->frameEndTime() - m_context->frameStartTime();
    bool shouldUseUtteranceLevel = visibleDuration > m_zoomThreshold;

    if (shouldUseUtteranceLevel != m_useUtteranceLevel) {
        setUseUtteranceLevel(shouldUseUtteranceLevel);
        reload();
    }
}

bool TranscriptListModel::useUtteranceLevel() const
{
    return m_useUtteranceLevel;
}

void TranscriptListModel::setUseUtteranceLevel(bool useUtterance)
{
    if (m_useUtteranceLevel == useUtterance) {
        return;
    }
    m_useUtteranceLevel = useUtterance;
    emit useUtteranceLevelChanged();
}

double TranscriptListModel::zoomThreshold() const
{
    return m_zoomThreshold;
}

void TranscriptListModel::setZoomThreshold(double threshold)
{
    if (muse::RealIsEqual(m_zoomThreshold, threshold)) {
        return;
    }
    m_zoomThreshold = threshold;
    emit zoomThresholdChanged();
    updateZoomLevel();
}

