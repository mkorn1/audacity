/*
* Audacity: A Digital Audio Editor
*/
#include "transcriptprojectextension.h"

#include <sqlite3.h>
#include <QJsonDocument>

#include "libraries/lib-project-file-io/ProjectFileIO.h"
#include "libraries/lib-project-file-io/DBConnection.h"
#include "libraries/lib-project-file-io/ProjectFileIOExtension.h"
#include "Project.h"
#include "itranscriptservice.h"
#include "transcriptjsonconverter.h"
#include "modularity/ioc.h"
#include "log.h"

using namespace au::chat;
using namespace muse;

namespace {
const char* TRANSCRIPT_TABLE_SCHEMA = 
    "CREATE TABLE IF NOT EXISTS main.transcript ("
    "  id INTEGER PRIMARY KEY,"
    "  data TEXT"
    ");";
}

TranscriptProjectExtension::TranscriptProjectExtension()
{
}

OnOpenAction TranscriptProjectExtension::OnOpen(AudacityProject& project, const std::string& path)
{
    UNUSED(project);
    LOGI() << "TranscriptProjectExtension::OnOpen() called for path: " << path;
    return OnOpenAction::Continue;
}

void TranscriptProjectExtension::OnLoad(AudacityProject& project)
{
    LOGI() << "TranscriptProjectExtension::OnLoad() called - starting transcript load process";
    ensureTranscriptTable(project);
    loadTranscript(project);
    LOGI() << "TranscriptProjectExtension::OnLoad() completed";
}

OnSaveAction TranscriptProjectExtension::OnSave(
    AudacityProject& project, const ProjectSaveCallback& projectSaveCallback)
{
    UNUSED(project);
    UNUSED(projectSaveCallback);
    LOGI() << "TranscriptProjectExtension::OnSave() called - preparing to save";
    return OnSaveAction::Continue;
}

OnCloseAction TranscriptProjectExtension::OnClose(AudacityProject& project)
{
    UNUSED(project);
    LOGI() << "TranscriptProjectExtension::OnClose() called";
    return OnCloseAction::Continue;
}

void TranscriptProjectExtension::OnUpdateSaved(
    AudacityProject& project, const ProjectSerializer& serializer)
{
    UNUSED(serializer);
    LOGI() << "TranscriptProjectExtension::OnUpdateSaved() called - saving transcript to database";
    ensureTranscriptTable(project);
    saveTranscript(project);
    LOGI() << "TranscriptProjectExtension::OnUpdateSaved() completed";
}

bool TranscriptProjectExtension::IsBlockLocked(
    const AudacityProject& project, int64_t blockId) const
{
    UNUSED(project);
    UNUSED(blockId);
    return false;
}

void TranscriptProjectExtension::ensureTranscriptTable(AudacityProject& project)
{
    LOGD() << "TranscriptProjectExtension::ensureTranscriptTable() - ensuring transcript table exists";
    auto& projectFileIO = ProjectFileIO::Get(project);
    
    if (!projectFileIO.HasConnection()) {
        LOGW() << "TranscriptProjectExtension: No database connection available";
        return;
    }
    
    sqlite3* db = projectFileIO.GetConnection().DB();
    
    if (!db) {
        LOGW() << "TranscriptProjectExtension: Failed to get database connection";
        return;
    }

    LOGD() << "TranscriptProjectExtension: Database connection obtained, creating table if needed";
    char* errmsg = nullptr;
    int rc = sqlite3_exec(db, TRANSCRIPT_TABLE_SCHEMA, nullptr, nullptr, &errmsg);
    
    if (rc != SQLITE_OK) {
        LOGE() << "TranscriptProjectExtension: Failed to create transcript table: " 
               << (errmsg ? errmsg : "unknown error");
        if (errmsg) {
            sqlite3_free(errmsg);
        }
    } else {
        LOGD() << "TranscriptProjectExtension: Transcript table ensured successfully";
    }
}

void TranscriptProjectExtension::saveTranscript(AudacityProject& project)
{
    LOGI() << "TranscriptProjectExtension::saveTranscript() - starting save operation";
    
    auto transcriptService = muse::modularity::_ioc()->resolve<ITranscriptService>("chat");
    if (!transcriptService) {
        LOGW() << "TranscriptProjectExtension::saveTranscript() - TranscriptService not available";
        return;
    }
    
    bool hasTranscript = transcriptService->hasTranscript();
    LOGI() << "TranscriptProjectExtension::saveTranscript() - hasTranscript: " << hasTranscript;
    
    if (!hasTranscript) {
        LOGI() << "TranscriptProjectExtension::saveTranscript() - No transcript to save, skipping";
        return;
    }

    auto transcript = transcriptService->transcript();
    LOGI() << "TranscriptProjectExtension::saveTranscript() - transcript has " 
           << transcript.words.size() << " words, " 
           << transcript.utterances.size() << " utterances";
    
    QJsonObject json = TranscriptJsonConverter::toJson(transcript);
    QJsonDocument doc(json);
    QByteArray jsonData = doc.toJson(QJsonDocument::Compact);
    
    LOGI() << "TranscriptProjectExtension::saveTranscript() - serialized to JSON, size: " 
           << jsonData.size() << " bytes";

    auto& projectFileIO = ProjectFileIO::Get(project);
    
    if (!projectFileIO.HasConnection()) {
        LOGW() << "TranscriptProjectExtension::saveTranscript() - No database connection available";
        return;
    }
    
    sqlite3* db = projectFileIO.GetConnection().DB();
    
    if (!db) {
        LOGW() << "TranscriptProjectExtension::saveTranscript() - Failed to get database connection";
        return;
    }

    LOGD() << "TranscriptProjectExtension::saveTranscript() - Database connection obtained, preparing statement";
    const char* sql = "INSERT INTO main.transcript(id, data) VALUES(1, ?1) "
                      "ON CONFLICT(id) DO UPDATE SET data = ?1;";
    
    sqlite3_stmt* stmt = nullptr;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr);
    
    if (rc != SQLITE_OK) {
        LOGE() << "TranscriptProjectExtension::saveTranscript() - Failed to prepare save statement: " 
               << sqlite3_errmsg(db);
        return;
    }

    LOGD() << "TranscriptProjectExtension::saveTranscript() - Statement prepared, binding data";
    // Use SQLITE_TRANSIENT since jsonData goes out of scope after this function
    rc = sqlite3_bind_text(stmt, 1, jsonData.constData(), jsonData.size(), SQLITE_TRANSIENT);
    if (rc != SQLITE_OK) {
        LOGE() << "TranscriptProjectExtension::saveTranscript() - Failed to bind text: " 
               << sqlite3_errmsg(db);
        sqlite3_finalize(stmt);
        return;
    }

    LOGD() << "TranscriptProjectExtension::saveTranscript() - Executing INSERT/UPDATE statement";
    rc = sqlite3_step(stmt);
    if (rc != SQLITE_DONE) {
        LOGE() << "TranscriptProjectExtension::saveTranscript() - Failed to execute save: " 
               << sqlite3_errmsg(db) << " (error code: " << rc << ")";
    } else {
        LOGI() << "TranscriptProjectExtension::saveTranscript() - SUCCESS: Saved transcript with " 
               << transcript.words.size() << " words, " 
               << transcript.utterances.size() << " utterances, "
               << jsonData.size() << " bytes to database";
    }

    sqlite3_finalize(stmt);
    LOGD() << "TranscriptProjectExtension::saveTranscript() - completed";
}

void TranscriptProjectExtension::loadTranscript(AudacityProject& project)
{
    LOGI() << "TranscriptProjectExtension::loadTranscript() - starting load operation";
    
    auto transcriptService = muse::modularity::_ioc()->resolve<ITranscriptService>("chat");
    if (!transcriptService) {
        LOGW() << "TranscriptProjectExtension::loadTranscript() - TranscriptService not available";
        return;
    }
    
    LOGI() << "TranscriptProjectExtension::loadTranscript() - TranscriptService available, "
           << "current hasTranscript: " << transcriptService->hasTranscript();

    auto& projectFileIO = ProjectFileIO::Get(project);
    
    if (!projectFileIO.HasConnection()) {
        LOGW() << "TranscriptProjectExtension::loadTranscript() - No database connection available";
        return;
    }
    
    sqlite3* db = projectFileIO.GetConnection().DB();
    
    if (!db) {
        LOGW() << "TranscriptProjectExtension::loadTranscript() - Failed to get database connection";
        return;
    }

    LOGD() << "TranscriptProjectExtension::loadTranscript() - Database connection obtained, querying for transcript";
    const char* sql = "SELECT data FROM main.transcript WHERE id = 1;";
    sqlite3_stmt* stmt = nullptr;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr);
    
    if (rc != SQLITE_OK) {
        LOGW() << "TranscriptProjectExtension::loadTranscript() - Failed to prepare load statement: " 
               << sqlite3_errmsg(db) << " (error code: " << rc << ")";
        return;
    }

    LOGD() << "TranscriptProjectExtension::loadTranscript() - Statement prepared, executing query";
    rc = sqlite3_step(stmt);
    if (rc == SQLITE_ROW) {
        LOGI() << "TranscriptProjectExtension::loadTranscript() - Found transcript row in database";
        const unsigned char* data = sqlite3_column_text(stmt, 0);
        int dataSize = sqlite3_column_bytes(stmt, 0);
        
        LOGI() << "TranscriptProjectExtension::loadTranscript() - Retrieved data size: " << dataSize << " bytes";
        
        if (data && dataSize > 0) {
            QByteArray jsonData(reinterpret_cast<const char*>(data), dataSize);
            LOGD() << "TranscriptProjectExtension::loadTranscript() - Parsing JSON data";
            QJsonDocument doc = QJsonDocument::fromJson(jsonData);
            
            if (!doc.isNull() && doc.isObject()) {
                QJsonObject json = doc.object();
                LOGD() << "TranscriptProjectExtension::loadTranscript() - Converting JSON to Transcript";
                Transcript transcript = TranscriptJsonConverter::fromJson(json);
                
                LOGI() << "TranscriptProjectExtension::loadTranscript() - Converted transcript has " 
                       << transcript.words.size() << " words, " 
                       << transcript.utterances.size() << " utterances";
                
                LOGI() << "TranscriptProjectExtension::loadTranscript() - Setting transcript in service";
                transcriptService->setTranscript(transcript);
                
                // Verify it was set correctly
                bool hasAfterSet = transcriptService->hasTranscript();
                LOGI() << "TranscriptProjectExtension::loadTranscript() - SUCCESS: Loaded and set transcript. "
                       << "hasTranscript after set: " << hasAfterSet 
                       << ", word count: " << transcript.words.size();
            } else {
                LOGW() << "TranscriptProjectExtension::loadTranscript() - Failed to parse transcript JSON. "
                       << "isNull: " << doc.isNull() 
                       << ", isObject: " << doc.isObject();
            }
        } else {
            LOGW() << "TranscriptProjectExtension::loadTranscript() - Row found but data is empty or null";
        }
    } else if (rc == SQLITE_DONE) {
        // No transcript in database - this is fine for new projects
        LOGI() << "TranscriptProjectExtension::loadTranscript() - No transcript found in project database "
               << "(SQLITE_DONE - this is normal for new projects)";
    } else {
        LOGW() << "TranscriptProjectExtension::loadTranscript() - Query failed: " 
               << sqlite3_errmsg(db) << " (error code: " << rc << ")";
    }

    sqlite3_finalize(stmt);
    LOGD() << "TranscriptProjectExtension::loadTranscript() - completed";
}

