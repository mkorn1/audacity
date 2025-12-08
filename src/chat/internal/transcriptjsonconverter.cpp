/*
* Audacity: A Digital Audio Editor
*/
#include "transcriptjsonconverter.h"

#include <QJsonArray>
#include "log.h"

using namespace au::chat;

Transcript TranscriptJsonConverter::fromJson(const QJsonObject& json)
{
    Transcript transcript;

    // Parse full text and duration
    transcript.fullText = muse::String::fromQString(json["full_text"].toString());
    transcript.duration = json["duration"].toDouble(0.0);
    transcript.fillerCount = json["filler_count"].toInt(0);

    // Parse words
    QJsonArray wordsArray = json["words"].toArray();
    for (const QJsonValue& wordValue : wordsArray) {
        QJsonObject wordObj = wordValue.toObject();
        TranscriptWord word;
        word.word = muse::String::fromQString(wordObj["word"].toString());
        word.startTime = wordObj["start_time"].toDouble(0.0);
        word.endTime = wordObj["end_time"].toDouble(0.0);
        word.confidence = wordObj["confidence"].toDouble(0.0);
        word.isFiller = wordObj["is_filler"].toBool(false);
        
        if (wordObj.contains("speaker")) {
            word.speaker = muse::String::fromQString(wordObj["speaker"].toString());
        }
        
        transcript.words.push_back(word);
    }

    // Parse utterances
    QJsonArray utterancesArray = json["utterances"].toArray();
    for (const QJsonValue& uttValue : utterancesArray) {
        QJsonObject uttObj = uttValue.toObject();
        TranscriptUtterance utterance;
        utterance.text = muse::String::fromQString(uttObj["text"].toString());
        utterance.startTime = uttObj["start_time"].toDouble(0.0);
        utterance.endTime = uttObj["end_time"].toDouble(0.0);
        
        if (uttObj.contains("speaker")) {
            utterance.speaker = muse::String::fromQString(uttObj["speaker"].toString());
        }

        // Parse words in utterance
        QJsonArray uttWordsArray = uttObj["words"].toArray();
        for (const QJsonValue& wordValue : uttWordsArray) {
            QJsonObject wordObj = wordValue.toObject();
            TranscriptWord word;
            word.word = muse::String::fromQString(wordObj["word"].toString());
            word.startTime = wordObj["start_time"].toDouble(0.0);
            word.endTime = wordObj["end_time"].toDouble(0.0);
            word.confidence = wordObj["confidence"].toDouble(0.0);
            word.isFiller = wordObj["is_filler"].toBool(false);
            
            if (wordObj.contains("speaker")) {
                word.speaker = muse::String::fromQString(wordObj["speaker"].toString());
            }
            
            utterance.words.push_back(word);
        }
        
        transcript.utterances.push_back(utterance);
    }

    return transcript;
}

QJsonObject TranscriptJsonConverter::toJson(const Transcript& transcript)
{
    QJsonObject json;
    json["full_text"] = QString::fromStdString(transcript.fullText.toStdString());
    json["duration"] = transcript.duration;
    json["filler_count"] = transcript.fillerCount;

    // Convert words
    QJsonArray wordsArray;
    for (const auto& word : transcript.words) {
        QJsonObject wordObj;
        wordObj["word"] = QString::fromStdString(word.word.toStdString());
        wordObj["start_time"] = word.startTime;
        wordObj["end_time"] = word.endTime;
        wordObj["confidence"] = word.confidence;
        wordObj["is_filler"] = word.isFiller;
        if (word.speaker.has_value()) {
            wordObj["speaker"] = QString::fromStdString(word.speaker->toStdString());
        }
        wordsArray.append(wordObj);
    }
    json["words"] = wordsArray;

    // Convert utterances
    QJsonArray utterancesArray;
    for (const auto& utterance : transcript.utterances) {
        QJsonObject uttObj;
        uttObj["text"] = QString::fromStdString(utterance.text.toStdString());
        uttObj["start_time"] = utterance.startTime;
        uttObj["end_time"] = utterance.endTime;
        if (utterance.speaker.has_value()) {
            uttObj["speaker"] = QString::fromStdString(utterance.speaker->toStdString());
        }

        QJsonArray uttWordsArray;
        for (const auto& word : utterance.words) {
            QJsonObject wordObj;
            wordObj["word"] = QString::fromStdString(word.word.toStdString());
            wordObj["start_time"] = word.startTime;
            wordObj["end_time"] = word.endTime;
            wordObj["confidence"] = word.confidence;
            wordObj["is_filler"] = word.isFiller;
            if (word.speaker.has_value()) {
                wordObj["speaker"] = QString::fromStdString(word.speaker->toStdString());
            }
            uttWordsArray.append(wordObj);
        }
        uttObj["words"] = uttWordsArray;
        utterancesArray.append(uttObj);
    }
    json["utterances"] = utterancesArray;

    return json;
}

