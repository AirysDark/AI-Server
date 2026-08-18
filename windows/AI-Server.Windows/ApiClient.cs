using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;

namespace AIServerWindows;

public sealed class ApiClient
{
    public const string DefaultBaseUrl = "https://ai-server.ddns.net";
    private readonly CookieContainer _cookies = new();
    private readonly HttpClient _http;
    private readonly JsonSerializerOptions _json = new() { PropertyNameCaseInsensitive = true, PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };

    public string BaseUrl { get; }
    public bool IsAuthenticated { get; private set; }
    public string? UserId { get; private set; }
    public string? ActiveAiId { get; private set; }

    public ApiClient(string? baseUrl = null)
    {
        BaseUrl = (baseUrl ?? DefaultBaseUrl).TrimEnd('/');
        var handler = new HttpClientHandler { UseCookies = true, CookieContainer = _cookies, AutomaticDecompression = DecompressionMethods.All };
        _http = new HttpClient(handler) { BaseAddress = new Uri(BaseUrl + "/"), Timeout = TimeSpan.FromMinutes(5) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("AI-Server-Windows/1.0");
    }

    public async Task<HealthResponse> HealthAsync(CancellationToken ct = default) => await GetAsync<HealthResponse>("api/health", ct) ?? new HealthResponse();

    public async Task<AuthMeResponse> MeAsync(CancellationToken ct = default)
    {
        var result = await GetAsync<AuthMeResponse>("api/auth/me", ct) ?? new AuthMeResponse();
        IsAuthenticated = result.Authenticated;
        UserId = result.UserId;
        ActiveAiId = result.Ais?.FirstOrDefault(x => x.Active)?.AiId;
        return result;
    }

    public Task<AuthResponse> LoginAsync(string email, string password, CancellationToken ct = default) => AuthenticateAsync("api/auth/login", email, password, null, ct);
    public Task<AuthResponse> RegisterAsync(string email, string password, string username, CancellationToken ct = default) => AuthenticateAsync("api/auth/register", email, password, username, ct);

    private async Task<AuthResponse> AuthenticateAsync(string path, string email, string password, string? username, CancellationToken ct)
    {
        var payload = new Dictionary<string, string> { ["email"] = email, ["password"] = password };
        if (username is not null) payload["username"] = username;
        using var response = await _http.PostAsJsonAsync(path, payload, _json, ct);
        var result = await ReadResponseAsync<AuthResponse>(response, ct);
        if (!response.IsSuccessStatusCode) throw new ApiException(result?.Error ?? response.ReasonPhrase ?? "Authentication failed", response.StatusCode);
        IsAuthenticated = true; UserId = result?.UserId; ActiveAiId = result?.Ais?.FirstOrDefault(x => x.Active)?.AiId;
        return result ?? new AuthResponse();
    }

    public async Task LogoutAsync(CancellationToken ct = default)
    {
        await PostAsync<object, object>("api/auth/logout", new { }, ct);
        IsAuthenticated = false; UserId = null; ActiveAiId = null;
    }

    public async Task<List<AiSummary>> GetAisAsync(CancellationToken ct = default) => (await GetAsync<AisResponse>("api/ais", ct))?.Ais ?? [];
    public async Task<ConversationResponse> GetConversationAsync(CancellationToken ct = default) => await GetAsync<ConversationResponse>("api/user", ct) ?? new ConversationResponse();

    public async Task SelectAiAsync(string aiId, CancellationToken ct = default)
    {
        var result = await PostAsync<SelectAiResponse, object>("api/ai/select", new { ai_id = aiId }, ct);
        if (result?.Ok != true) throw new ApiException("AI could not be selected", HttpStatusCode.BadRequest);
        ActiveAiId = aiId;
    }

    public async Task<string> CreateAiAsync(CancellationToken ct = default)
    {
        var result = await PostAsync<CreateAiResponse, object>("api/ai/create", new { }, ct);
        if (result?.Ok != true || string.IsNullOrWhiteSpace(result.AiId)) throw new ApiException("AI could not be created", HttpStatusCode.BadRequest);
        ActiveAiId = result.AiId; return result.AiId;
    }

    public async Task DeleteAiAsync(string aiId, CancellationToken ct = default)
    {
        var result = await PostAsync<BasicResponse, object>("api/ai/delete", new { ai_id = aiId }, ct);
        if (result?.Ok != true) throw new ApiException("AI could not be deleted", HttpStatusCode.BadRequest);
    }

    public async Task<AiSettings> GetSettingsAsync(CancellationToken ct = default) => await GetAsync<AiSettings>("api/settings", ct) ?? new AiSettings();
    public async Task<AiSettings> SaveSettingsAsync(AiSettings settings, CancellationToken ct = default) => await PostAsync<AiSettings, AiSettings>("api/settings", settings, ct) ?? settings;

    public async Task<ChatResponse> ChatAsync(string message, string? imagePath = null, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(imagePath)) return await PostAsync<ChatResponse, object>("chat", new { message }, ct) ?? new ChatResponse();
        using var form = new MultipartFormDataContent();
        form.Add(new StringContent(message ?? string.Empty), "message");
        await using var stream = File.OpenRead(imagePath);
        using var file = new StreamContent(stream);
        file.Headers.ContentType = new MediaTypeHeaderValue(GetMimeType(imagePath));
        form.Add(file, "file", Path.GetFileName(imagePath));
        using var response = await _http.PostAsync("chat", form, ct);
        var result = await ReadResponseAsync<ChatResponse>(response, ct);
        if (!response.IsSuccessStatusCode) throw new ApiException(result?.Error ?? response.ReasonPhrase ?? "Chat request failed", response.StatusCode);
        return result ?? new ChatResponse();
    }

    public Task<string?> UploadProfilePhotoAsync(string filePath, CancellationToken ct = default) => UploadFileAsync("api/profile_photo", filePath, true, ct);
    public Task<string?> UploadAiPhotoAsync(string filePath, CancellationToken ct = default) => UploadFileAsync("api/ai_photo", filePath, false, ct);

    private async Task<string?> UploadFileAsync(string path, string filePath, bool profile, CancellationToken ct)
    {
        using var form = new MultipartFormDataContent();
        await using var stream = File.OpenRead(filePath);
        using var file = new StreamContent(stream);
        file.Headers.ContentType = new MediaTypeHeaderValue(GetMimeType(filePath));
        form.Add(file, "file", Path.GetFileName(filePath));
        using var response = await _http.PostAsync(path, form, ct);
        var result = await ReadResponseAsync<UploadResponse>(response, ct);
        if (!response.IsSuccessStatusCode) throw new ApiException(result?.Error ?? response.ReasonPhrase ?? "Upload failed", response.StatusCode);
        return profile ? result?.ProfilePhoto : result?.Image;
    }

    public string ResolveUrl(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) return BaseUrl;
        if (Uri.TryCreate(path, UriKind.Absolute, out var absolute)) return absolute.ToString();
        return BaseUrl + "/" + path.TrimStart('/');
    }

    private async Task<T?> GetAsync<T>(string path, CancellationToken ct)
    {
        using var response = await _http.GetAsync(path, ct);
        var result = await ReadResponseAsync<T>(response, ct);
        if (!response.IsSuccessStatusCode) throw new ApiException(GetError(result, response), response.StatusCode);
        return result;
    }

    private async Task<TResponse?> PostAsync<TResponse, TRequest>(string path, TRequest request, CancellationToken ct)
    {
        using var response = await _http.PostAsJsonAsync(path, request, _json, ct);
        var result = await ReadResponseAsync<TResponse>(response, ct);
        if (!response.IsSuccessStatusCode) throw new ApiException(GetError(result, response), response.StatusCode);
        return result;
    }

    private async Task<T?> ReadResponseAsync<T>(HttpResponseMessage response, CancellationToken ct)
    {
        var text = await response.Content.ReadAsStringAsync(ct);
        if (string.IsNullOrWhiteSpace(text)) return default;
        try { return JsonSerializer.Deserialize<T>(text, _json); } catch (JsonException) { return default; }
    }

    private static string GetError<T>(T? result, HttpResponseMessage response) => result is ErrorResponse error && !string.IsNullOrWhiteSpace(error.Error) ? error.Error : response.ReasonPhrase ?? "Server request failed";
    private static string GetMimeType(string path) => Path.GetExtension(path).ToLowerInvariant() switch { ".jpg" or ".jpeg" => "image/jpeg", ".png" => "image/png", ".webp" => "image/webp", ".gif" => "image/gif", _ => "application/octet-stream" };
}

public sealed class ApiException(string message, HttpStatusCode statusCode) : Exception(message) { public HttpStatusCode StatusCode { get; } = statusCode; }
