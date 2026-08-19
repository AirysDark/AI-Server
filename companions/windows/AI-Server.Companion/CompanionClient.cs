using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;

namespace AiServer.Companion;

public sealed class CompanionClient
{
    private readonly CookieContainer _cookies = new();
    private readonly HttpClient _http;
    private CancellationTokenSource? _cts;

    public string BaseUrl { get; set; } = "https://ai-server.ddns.net";
    public string? ActiveAiId { get; private set; }
    public string? ActiveAiName { get; private set; }
    public event Action<string,string>? MessageReceived;
    public event Action<bool>? ConnectionChanged;

    public CompanionClient()
    {
        var handler = new HttpClientHandler { UseCookies = true, CookieContainer = _cookies, AutomaticDecompression = DecompressionMethods.All };
        _http = new HttpClient(handler) { Timeout = TimeSpan.FromMinutes(5) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("AI-Server-Companion/1.0");
    }

    public Task LoginAsync(string email, string password) => AuthenticateAsync("api/auth/login", new { email, password });
    public Task RegisterAsync(string email, string password, string username) => AuthenticateAsync("api/auth/register", new { email, password, username });

    private async Task AuthenticateAsync(string path, object payload)
    {
        using var response = await _http.PostAsJsonAsync(BaseUrl.TrimEnd('/') + "/" + path, payload);
        var body = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode) throw new InvalidOperationException(ReadError(body, "Authentication failed."));
        await LoadSelectedAiAsync();
    }

    public async Task<List<AiChoice>> GetAisAsync()
    {
        using var response = await _http.GetAsync(BaseUrl.TrimEnd('/') + "/api/ais");
        var body = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode) throw new InvalidOperationException(ReadError(body, "Unable to load AIs."));
        try
        {
            using var json = JsonDocument.Parse(body);
            var root = json.RootElement;
            var array = root.ValueKind == JsonValueKind.Array ? root : root.TryGetProperty("ais", out var a) ? a : default;
            var result = new List<AiChoice>();
            if (array.ValueKind != JsonValueKind.Array) return result;
            foreach (var item in array.EnumerateArray())
            {
                var id = item.TryGetProperty("ai_id", out var i) ? i.GetString() : null;
                if (string.IsNullOrWhiteSpace(id)) continue;
                var name = item.TryGetProperty("ai_name", out var n) ? n.GetString() : "AI";
                var active = item.TryGetProperty("active", out var ac) && ac.ValueKind == JsonValueKind.True;
                result.Add(new AiChoice(id!, name ?? "AI", active));
            }
            return result;
        }
        catch { return []; }
    }

    public async Task SelectAiAsync(string aiId)
    {
        using var response = await _http.PostAsJsonAsync(BaseUrl.TrimEnd('/') + "/api/ai/select", new { ai_id = aiId });
        var body = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode) throw new InvalidOperationException(ReadError(body, "AI selection failed."));
        ActiveAiId = aiId;
        var ai = (await GetAisAsync()).FirstOrDefault(x => x.AiId == aiId);
        ActiveAiName = ai?.AiName ?? "AI";
    }

    public async Task<bool> ConnectAsync()
    {
        try
        {
            using var response = await _http.GetAsync(BaseUrl.TrimEnd('/') + "/api/auth/me");
            if (!response.IsSuccessStatusCode) { ConnectionChanged?.Invoke(false); return false; }
            await LoadSelectedAiAsync();
            ConnectionChanged?.Invoke(true);
            return true;
        }
        catch { ConnectionChanged?.Invoke(false); return false; }
    }

    private async Task LoadSelectedAiAsync()
    {
        try
        {
            using var response = await _http.GetAsync(BaseUrl.TrimEnd('/') + "/api/auth/me");
            using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            if (!json.RootElement.TryGetProperty("ais", out var ais) || ais.ValueKind != JsonValueKind.Array) return;
            foreach (var ai in ais.EnumerateArray())
            {
                if (ai.TryGetProperty("active", out var active) && active.ValueKind == JsonValueKind.True)
                {
                    ActiveAiId = ai.TryGetProperty("ai_id", out var id) ? id.GetString() : null;
                    ActiveAiName = ai.TryGetProperty("ai_name", out var name) ? name.GetString() : "AI";
                    return;
                }
            }
        }
        catch { }
    }

    public async Task SendAsync(string text)
    {
        using var response = await _http.PostAsync(BaseUrl.TrimEnd('/') + "/chat", new StringContent(JsonSerializer.Serialize(new { message = text }), Encoding.UTF8, "application/json"));
        var body = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode) throw new InvalidOperationException(ReadError(body, "Message failed."));
        try
        {
            using var json = JsonDocument.Parse(body);
            var reply = json.RootElement.TryGetProperty("reply", out var r) ? r.GetString() : null;
            if (!string.IsNullOrWhiteSpace(reply)) MessageReceived?.Invoke(ActiveAiName ?? "AI", reply!);
        }
        catch { }
    }

    public async Task StartLiveAsync()
    {
        _cts?.Cancel(); _cts = new CancellationTokenSource();
        while (!_cts.IsCancellationRequested)
        {
            try
            {
                using var response = await _http.GetAsync(BaseUrl.TrimEnd('/') + "/api/companion/events", _cts.Token);
                if (response.IsSuccessStatusCode)
                {
                    var body = await response.Content.ReadAsStringAsync(_cts.Token);
                    foreach (var line in body.Split('\n', StringSplitOptions.RemoveEmptyEntries))
                    {
                        try
                        {
                            using var json = JsonDocument.Parse(line);
                            var name = json.RootElement.TryGetProperty("ai_name", out var n) ? n.GetString() ?? ActiveAiName ?? "AI" : ActiveAiName ?? "AI";
                            var text = json.RootElement.TryGetProperty("text", out var t) ? t.GetString() : null;
                            if (!string.IsNullOrWhiteSpace(text)) MessageReceived?.Invoke(name, text!);
                        }
                        catch { }
                    }
                }
            }
            catch (OperationCanceledException) { break; }
            catch { ConnectionChanged?.Invoke(false); try { await Task.Delay(3000, _cts.Token); } catch { break; } }
        }
    }

    public void StopLive() => _cts?.Cancel();

    private static string ReadError(string body, string fallback)
    {
        try
        {
            using var json = JsonDocument.Parse(body);
            foreach (var key in new[] { "error", "message", "detail" })
                if (json.RootElement.TryGetProperty(key, out var value) && value.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(value.GetString())) return value.GetString()!;
        }
        catch { }
        return fallback;
    }
}

public sealed record AiChoice(string AiId, string AiName, bool Active);
