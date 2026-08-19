#include "chat.h"

void ChatManager::begin() {
    _state = ChatState{};
}

void ChatManager::setConversation(const String& id) {
    _state.conversationId = id;
}

void ChatManager::setAi(const String& ai) {
    _state.selectedAi = ai;
}

void ChatManager::setUserMessage(const String& message) {
    _state.lastUserMessage = message;
    _state.generating = true;
}

void ChatManager::setAiMessage(const String& message) {
    _state.lastAiMessage = message;
    _state.generating = false;
}
