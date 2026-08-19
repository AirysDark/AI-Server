using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Net.Http.Json;

namespace AiServer.Companion;

public sealed class CompanionClient
{
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(30) };
    public string BaseUrl { get; set; } = "https://ai-server.ddns.net";
    public event Action<string,string>? MessageReceived;
    public event Action<bool>? ConnectionChanged;
    private CancellationTokenSource? _cts;

    public async Task<bool> ConnectAsync()
    {
        try
        {
            using var response = await _http.GetAsync(BaseUrl.TrimEnd('/') + "/api/auth/me");
            ConnectionChanged?.Invoke(response.IsSuccessStatusCode);
            return response.IsSuccessStatusCode;
        }
        catch { ConnectionChanged?.Invoke(false); return false; }
    }

    public async Task SendAsync(string text)
    {
        var payload = JsonSerializer.Serialize(new { message = text });
        using var response = await _http.PostAsync(BaseUrl.TrimEnd('/') + "/chat", new StringContent(payload, Encoding.UTF8, "application/json"));
        response.EnsureSuccessStatusCode();
        var body = await response.Content.ReadAsStringAsync();
        try
        {
            using var json = JsonDocument.Parse(body);
            var reply = json.RootElement.TryGetProperty("reply", out var r) ? r.GetString() : null;
            if (!string.IsNullOrWhiteSpace(reply)) MessageReceived?.Invoke("AI", reply);
        }
        catch { }
    }

    public async Task StartLiveAsync()
    {
        _cts?.Cancel();
        _cts = new CancellationTokenSource();
        while (!_cts.IsCancellationRequested)
        {
            try
            {
                using var response = await _http.GetAsync(BaseUrl.TrimEnd('/') + "/api/companion/events", _cts.Token);
                if (response.IsSuccessStatusCode)
                {
                    var body = await response.Content.ReadAsStringAsync(_cts.Token);
                    if (!string.IsNullOrWhiteSpace(body))
                    {
                        foreach (var line in body.Split('\n', StringSplitOptions.RemoveEmptyEntries))
                        {
                            try
                            {
                                using var json = JsonDocument.Parse(line);
                                var name = json.RootElement.TryGetProperty("ai_name", out var n) ? n.GetString() ?? "AI" : "AI";
                                var text = json.RootElement.TryGetProperty("text", out var t) ? t.GetString() : null;
                                if (!string.IsNullOrWhiteSpace(text)) MessageReceived?.Invoke(name, text!);
                            }
                            catch { }
                        }
                    }
                }
            }
            catch (OperationCanceledException) { break; }
            catch { ConnectionChanged?.Invoke(false); await Task.Delay(3000, _cts.Token); }
        }
    }

    public void StopLive() => _cts?.Cancel();
}
