/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "trackitemslistmodel.h"
#include "modularity/ioc.h"
#include "chat/itranscriptservice.h"
#include "chat/dom/transcript.h"

namespace au::projectscene {
class TranscriptWordItem;

class TranscriptListModel : public TrackItemsListModel
{
    Q_OBJECT

    Q_PROPERTY(bool useUtteranceLevel READ useUtteranceLevel WRITE setUseUtteranceLevel NOTIFY useUtteranceLevelChanged FINAL)
    Q_PROPERTY(double zoomThreshold READ zoomThreshold WRITE setZoomThreshold NOTIFY zoomThresholdChanged FINAL)

    muse::Inject<au::chat::ITranscriptService> transcriptService;

public:
    explicit TranscriptListModel(QObject* parent = nullptr);

    bool useUtteranceLevel() const;
    void setUseUtteranceLevel(bool useUtterance);

    double zoomThreshold() const;
    void setZoomThreshold(double threshold);

signals:
    void useUtteranceLevelChanged();
    void zoomThresholdChanged();

private:
    void onInit() override;
    void onReload() override;

    void update();
    void updateItemMetrics(ViewTrackItem* item) override;
    trackedit::TrackItemKeyList getSelectedItemKeys() const override;

    void updateZoomLevel();
    void checkAndReloadIfNeeded();

    bool m_useUtteranceLevel = false;
    double m_zoomThreshold = 5.0; // seconds visible - switch to word level below this
    au::chat::Transcript m_transcript;
    
    // Track the last loaded time range to detect when we need to reload
    double m_lastLoadedStartTime = -1.0;
    double m_lastLoadedEndTime = -1.0;
};
}

