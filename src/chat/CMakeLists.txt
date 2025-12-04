#
# Audacity: A Digital Audio Editor
#

declare_module(chat)

set(MODULE_QRC chat.qrc)

set(MODULE_QML_IMPORT ${CMAKE_CURRENT_LIST_DIR}/qml)

set(MODULE_SRC
    ${CMAKE_CURRENT_LIST_DIR}/chatmodule.cpp
    ${CMAKE_CURRENT_LIST_DIR}/chatmodule.h
    ${CMAKE_CURRENT_LIST_DIR}/chattypes.h
    ${CMAKE_CURRENT_LIST_DIR}/ichatcontroller.h
    ${CMAKE_CURRENT_LIST_DIR}/iagentactionexecutor.h
    ${CMAKE_CURRENT_LIST_DIR}/iagentstatereader.h
    ${CMAKE_CURRENT_LIST_DIR}/iagentfeedbackprovider.h

    ${CMAKE_CURRENT_LIST_DIR}/internal/chatcontroller.cpp
    ${CMAKE_CURRENT_LIST_DIR}/internal/chatcontroller.h
    ${CMAKE_CURRENT_LIST_DIR}/internal/agentactionexecutor.cpp
    ${CMAKE_CURRENT_LIST_DIR}/internal/agentactionexecutor.h
    ${CMAKE_CURRENT_LIST_DIR}/internal/agentstatereader.cpp
    ${CMAKE_CURRENT_LIST_DIR}/internal/agentstatereader.h
    ${CMAKE_CURRENT_LIST_DIR}/internal/agentfeedbackprovider.cpp
    ${CMAKE_CURRENT_LIST_DIR}/internal/agentfeedbackprovider.h
    ${CMAKE_CURRENT_LIST_DIR}/internal/pythonbridge.cpp
    ${CMAKE_CURRENT_LIST_DIR}/internal/pythonbridge.h
    ${CMAKE_CURRENT_LIST_DIR}/internal/pythonbridge_impl.h

    ${CMAKE_CURRENT_LIST_DIR}/view/chatviewmodel.cpp
    ${CMAKE_CURRENT_LIST_DIR}/view/chatviewmodel.h
    )

set(MODULE_LINK
    trackedit
    effects_base
    playback
    project
    context
)

set(MODULE_USE_UNITY OFF)

setup_module()

