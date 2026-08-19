using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace AiServer.Companion;

public sealed class CompanionClient
{
    private readonly CookieContainer _cookies = new();
    private readonly HttpClient _http;
    private CancellationTokenSource? _cts;

    public string BaseUrl { get; set; } = "https://ai-server.ddns.net";
    public string? ActiveAiId { get; private set; }
    public string? ActiveAiName { get; private set; }
    public string? ActiveAiPhoto { get; private set; }
    public event Action<string, string>? MessageReceived;
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
            JsonElement array;
            if (root.ValueKind == JsonValueKind.Array) array = root;
            else if (root.TryGetProperty("ais", out var aisProperty) && aisProperty.ValueKind == JsonValueKind.Array) array = aisProperty;
            else return new List<AiChoice>();

            var result = new List<AiChoice>();
            for (var index = 0; index < array.GetArrayLength(); index++)
            {
                var item = array[index];
                var id = item.TryGetProperty("ai_id", out var idProperty) ? idProperty.GetString() : null;
                if (string.IsNullOrWhiteSpace(id)) continue;
                var name = item.TryGetProperty("ai_name", out var nameProperty) ? nameProperty.GetString() : "AI";
                var active = item.TryGetProperty("active", out var activeProperty) && activeProperty.ValueKind == JsonValueKind.True;
                var photo = item.TryGetProperty("profile_photo", out var photoProperty) ? photoProperty.GetString() : null;
                result.Add(new AiChoice(id, name ?? "AI", active, photo));
            }
            return result;
        }
        catch (JsonException) { return new List<AiChoice>(); }
    }

    public async Task SelectAiAsync(string aiId)
    {
        using var response = await _http.PostAsJsonAsync(BaseUrl.TrimEnd('/') + "/api/ai/select", new { ai_id = aiId });
        var body = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode) throw new InvalidOperationException(ReadError(body, "AI selection failed."));
        ActiveAiId = aiId;
        var ai = (await GetAisAsync()).FirstOrDefault(x => x.AiId == aiId);
        if (ai != null) { ActiveAiName = ai.AiName; ActiveAiPhoto = ai.ProfilePhoto; }
    }

    public async Task<bool> ConnectAsync()
    {
        try
        {
            using var response = await _http.GetAsync(BaseUrl.TrimEnd('/') + "/api/auth/me");
            if (!response.IsSuccessStatusCode) { ConnectionChanged?.Invoke(false); return false; }
            await LoadSelectedAiAsync(); ConnectionChanged?.Invoke(true); return true;
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
            for (var index = 0; index < ais.GetArrayLength(); index++)
            {
                var ai = ais[index];
                if (!ai.TryGetProperty("active", out var active) || active.ValueKind != JsonValueKind.True) continue;
                ActiveAiId = ai.TryGetProperty("ai_id", out var id) ? id.GetString() : null;
                ActiveAiName = ai.TryGetProperty("ai_name", out var name) ? name.GetString() : "AI";
                ActiveAiPhoto = ai.TryGetProperty("profile_photo", out var photo) ? photo.GetString() : null;
                return;
            }
        }
        catch { }
    }

    public async Task SendAsync(string text)
    {
        var payload = JsonSerializer.Serialize(new { message = text });
        using var content = new StringContent(payload, Encoding.UTF8, "application/json");
        using var response = await _http.PostAsync(BaseUrl.TrimEnd('/') + "/chat", content);
        var body = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode) throw new InvalidOperationException(ReadError(body, "Message failed."));
        try
        {
            using var json = JsonDocument.Parse(body);
            var reply = json.RootElement.TryGetProperty("reply", out var replyProperty) ? replyProperty.GetString() : null;
            if (!string.IsNullOrWhiteSpace(reply)) MessageReceived?.Invoke(ActiveAiName ?? "AI", reply);
        }
        catch (JsonException) { }
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
                    var lines = body.Split('\n', StringSplitOptions.RemoveEmptyEntries);
                    for (var index = 0; index < lines.Length; index++)
                    {
                        var line = lines[index].Trim(); if (line.Length == 0) continue;
                        try
                        {
                            using var json = JsonDocument.Parse(line);
                            var name = json.RootElement.TryGetProperty("ai_name", out var nameProperty) ? nameProperty.GetString() ?? ActiveAiName ?? "AI" : ActiveAiName ?? "AI";
                            var text = json.RootElement.TryGetProperty("text", out var textProperty) ? textProperty.GetString() : null;
                            if (!string.IsNullOrWhiteSpace(text)) MessageReceived?.Invoke(name, text);
                        }
                        catch (JsonException) { }
                    }
                }
            }
            catch (OperationCanceledException) { break; }
            catch
            {
                ConnectionChanged?.Invoke(false);
                try { await Task.Delay(TimeSpan.FromSeconds(3), _cts.Token); } catch { break; }
            }
        }
    }

    public void StopLive() => _cts?.Cancel();
    public string ResolveUrl(string? path) => string.IsNullOrWhiteSpace(path) ? "" : path.StartsWith("http", StringComparison.OrdinalIgnoreCase) ? path : BaseUrl.TrimEnd('/') + "/" + path.TrimStart('/');

    public async Task<byte[]?> GetImageAsync(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) return null;
        try { return await _http.GetByteArrayAsync(ResolveUrl(path)); } catch { return null; }
    }

    private static string ReadError(string body, string fallback)
    {
        try
        {
            using var json = JsonDocument.Parse(body);
            var keys = new[] { "error", "message", "detail" };
            for (var index = 0; index < keys.Length; index++)
                if (json.RootElement.TryGetProperty(keys[index], out var value) && value.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(value.GetString())) return value.GetString()!;
        }
        catch (JsonException) { }
        return fallback;
    }
}

public sealed record AiChoice(string AiId, string AiName, bool Active, string? ProfilePhoto);
