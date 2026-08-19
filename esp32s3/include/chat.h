#pragma once

#include <Arduino.h>

struct ChatState {
    String conversationId;
    String selectedAi;
    String lastUserMessage;
    String lastAiMessage;
    bool generating = false;
};

class ChatManager {
public:
    void begin();
    void setConversation(const String& id);
    void setAi(const String& ai);
    void setUserMessage(const String& message);
    void setAiMessage(const String& message);
    ChatState& state() { return _state; }

private:
    ChatState _state;
};
