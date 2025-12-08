/*
* Audacity: A Digital Audio Editor
*/
#pragma once

#include <QJsonObject>
#include "dom/transcript.h"

namespace au::chat {
class TranscriptJsonConverter
{
public:
    static Transcript fromJson(const QJsonObject& json);
    static QJsonObject toJson(const Transcript& transcript);
};
}

