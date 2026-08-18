namespace AIServerWindows;

public class ErrorResponse { public string? Error { get; set; } }
public class HealthResponse { public bool Ok { get; set; } public string? Server { get; set; } public string? Host { get; set; } public int Port { get; set; } public string? Url { get; set; } public string? LanIp { get; set; } }
public class AuthResponse : ErrorResponse { public bool Ok { get; set; } public string? UserId { get; set; } public List<AiSummary>? Ais { get; set; } }
public class AuthMeResponse : ErrorResponse { public bool Authenticated { get; set; } public string? UserId { get; set; } public string? Email { get; set; } public string? Username { get; set; } public int MaxAis { get; set; } public List<AiSummary>? Ais { get; set; } }
public class AisResponse : ErrorResponse { public List<AiSummary>? Ais { get; set; } public int Max { get; set; } }
public class AiSummary { public string? AiId { get; set; } public string? AiName { get; set; } public string? ProfilePhoto { get; set; } public bool SetupComplete { get; set; } public double Created { get; set; } public bool Active { get; set; } public override string ToString() => AiName ?? AiId ?? "AI"; }
public class SelectAiResponse : ErrorResponse { public bool Ok { get; set; } public string? AiId { get; set; } }
public class CreateAiResponse : ErrorResponse { public bool Ok { get; set; } public string? AiId { get; set; } }
public class BasicResponse : ErrorResponse { public bool Ok { get; set; } }
public class UploadResponse : ErrorResponse { public bool Ok { get; set; } public string? ProfilePhoto { get; set; } public string? Image { get; set; } }
public class ChatResponse : ErrorResponse { public string? Reply { get; set; } public string? UserId { get; set; } public string? AiId { get; set; } public string? Image { get; set; } }
public class ConversationResponse { public List<ConversationEntry>? Conversation { get; set; } public Dictionary<string, object>? Memory { get; set; } public Dictionary<string, object>? ProactiveState { get; set; } }
public class ConversationEntry { public string? User { get; set; } public string? Ai { get; set; } public string? Timestamp { get; set; } public string? Image { get; set; } public string? Trigger { get; set; } }

public class AiSettings
{
    public string? UserId { get; set; }
    public string? AiId { get; set; }
    public bool SetupComplete { get; set; }
    public string? AiName { get; set; }
    public string? ProfilePhoto { get; set; }
    public string? Description { get; set; }
    public string? Background { get; set; }
    public string? UserInformation { get; set; }
    public string? UserName { get; set; }
    public string? Personality { get; set; }
    public string? Instructions { get; set; }
    public AiConfig Config { get; set; } = new();
    public AiFeatures Features { get; set; } = new();
    public ProactiveSettings Proactive { get; set; } = new();
}
public class AiConfig { public List<string> Traits { get; set; } = []; public List<string> Rules { get; set; } = []; }
public class AiFeatures { public bool OnlineAi { get; set; } = true; public bool Learning { get; set; } = true; public bool LongTermMemory { get; set; } = true; public bool RelevantMemory { get; set; } = true; public bool AutomaticImages { get; set; } public bool ProactiveImages { get; set; } }
public class ProactiveSettings { public bool Enabled { get; set; } }
public class ChatMessage { public string Role { get; set; } = "AI"; public string Text { get; set; } = ""; public string? Image { get; set; } }
