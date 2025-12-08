/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include "viewtrackitem.h"
#include "chat/dom/transcript.h"

namespace au::projectscene {
class TranscriptWordItem : public ViewTrackItem
{
    Q_OBJECT

    Q_PROPERTY(bool isFiller READ isFiller NOTIFY isFillerChanged FINAL)
    Q_PROPERTY(double confidence READ confidence NOTIFY confidenceChanged FINAL)

public:
    explicit TranscriptWordItem(QObject* parent);

    void setWord(const au::chat::TranscriptWord& word);
    void setUtterance(const au::chat::TranscriptUtterance& utterance);

    bool isFiller() const;
    double confidence() const;

signals:
    void isFillerChanged();
    void confidenceChanged();

private:
    bool m_isFiller = false;
    double m_confidence = 0.0;
};
}

