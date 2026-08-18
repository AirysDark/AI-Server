using System.Collections.ObjectModel;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media.Imaging;
using Microsoft.Win32;

namespace AIServerWindows;

public partial class MainWindow : Window
{
    private readonly ApiClient _api = new();
    private string? _attachedImage;
    private bool _changingAi;
    public ObservableCollection<ChatMessage> Messages { get; } = [];

    public MainWindow()
    {
        InitializeComponent();
        DataContext = this;
        Loaded += MainWindow_Loaded;
    }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        try
        {
            var health = await _api.HealthAsync();
            LoginStatus.Text = health.Ok ? $"Connected to {health.Host}" : "Server responded, but health check failed.";
        }
        catch (Exception ex) { LoginStatus.Text = "Server unavailable: " + ex.Message; }
    }

    private async void Login_Click(object sender, RoutedEventArgs e) => await Authenticate(() => _api.LoginAsync(EmailBox.Text.Trim(), PasswordBox.Password));
    private async void Register_Click(object sender, RoutedEventArgs e) => await Authenticate(() => _api.RegisterAsync(EmailBox.Text.Trim(), PasswordBox.Password, UsernameBox.Text.Trim()));

    private async Task Authenticate(Func<Task<AuthResponse>> action)
    {
        try { SetLoginEnabled(false); LoginStatus.Text = "Connecting..."; await action(); await ShowMainAsync(); }
        catch (Exception ex) { LoginStatus.Text = ex.Message; }
        finally { SetLoginEnabled(true); }
    }

    private void SetLoginEnabled(bool enabled)
    {
        EmailBox.IsEnabled = enabled; UsernameBox.IsEnabled = enabled; PasswordBox.IsEnabled = enabled;
    }

    private async Task ShowMainAsync()
    {
        LoginView.Visibility = Visibility.Collapsed;
        MainView.Visibility = Visibility.Visible;
        await RefreshAisAsync();
        await LoadCurrentAiAsync();
    }

    private async Task RefreshAisAsync()
    {
        var ais = await _api.GetAisAsync();
        _changingAi = true;
        AiSelector.ItemsSource = ais;
        var selected = ais.FirstOrDefault(x => x.AiId == _api.ActiveAiId) ?? ais.FirstOrDefault(x => x.Active) ?? ais.FirstOrDefault();
        if (selected is not null) AiSelector.SelectedItem = selected;
        _changingAi = false;
    }

    private async Task LoadCurrentAiAsync()
    {
        try
        {
            var settings = await _api.GetSettingsAsync();
            AiNameText.Text = string.IsNullOrWhiteSpace(settings.AiName) ? "AI" : settings.AiName;
            SettingName.Text = settings.AiName ?? "";
            SettingDescription.Text = settings.Description ?? "";
            SettingPersonality.Text = settings.Personality ?? "";
            SettingInstructions.Text = settings.Instructions ?? "";
            OnlineAiCheck.IsChecked = settings.Features.OnlineAi;
            LearningCheck.IsChecked = settings.Features.Learning;
            MemoryCheck.IsChecked = settings.Features.LongTermMemory;
            RelevantMemoryCheck.IsChecked = settings.Features.RelevantMemory;
            AutoImagesCheck.IsChecked = settings.Features.AutomaticImages;
            await SetAiPhotoAsync(settings.ProfilePhoto);
            await LoadConversationAsync();
        }
        catch (Exception ex) { ServerStatus.Text = ex.Message; }
    }

    private async Task LoadConversationAsync()
    {
        Messages.Clear();
        var history = await _api.GetConversationAsync();
        foreach (var entry in history.Conversation ?? [])
        {
            if (!string.IsNullOrWhiteSpace(entry.User)) Messages.Add(new ChatMessage { Role = "You", Text = entry.User });
            if (!string.IsNullOrWhiteSpace(entry.Ai)) Messages.Add(new ChatMessage { Role = AiNameText.Text, Text = entry.Ai, Image = entry.Image });
        }
        EmptyChatText.Visibility = Messages.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
        if (Messages.Count > 0) MessagesList.ScrollIntoView(Messages[^1]);
    }

    private async void AiSelector_SelectionChanged(object sender, System.Windows.Controls.SelectionChangedEventArgs e)
    {
        if (_changingAi || AiSelector.SelectedItem is not AiSummary ai || string.IsNullOrWhiteSpace(ai.AiId)) return;
        try { _changingAi = true; await _api.SelectAiAsync(ai.AiId); await LoadCurrentAiAsync(); }
        catch (Exception ex) { ServerStatus.Text = ex.Message; }
        finally { _changingAi = false; }
    }

    private async void CreateAi_Click(object sender, RoutedEventArgs e)
    {
        try { await _api.CreateAiAsync(); await RefreshAisAsync(); await LoadCurrentAiAsync(); }
        catch (Exception ex) { ServerStatus.Text = ex.Message; }
    }

    private async void Logout_Click(object sender, RoutedEventArgs e)
    {
        try { await _api.LogoutAsync(); } catch { }
        Messages.Clear(); MainView.Visibility = Visibility.Collapsed; LoginView.Visibility = Visibility.Visible; LoginStatus.Text = "Logged out.";
    }

    private void Settings_Click(object sender, RoutedEventArgs e) => SettingsColumn.Width = SettingsColumn.Width.Value == 0 ? new GridLength(330) : new GridLength(0);

    private async void SaveSettings_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var settings = await _api.GetSettingsAsync();
            settings.AiName = SettingName.Text.Trim();
            settings.Description = SettingDescription.Text;
            settings.Personality = SettingPersonality.Text;
            settings.Instructions = SettingInstructions.Text;
            settings.Features.OnlineAi = OnlineAiCheck.IsChecked == true;
            settings.Features.Learning = LearningCheck.IsChecked == true;
            settings.Features.LongTermMemory = MemoryCheck.IsChecked == true;
            settings.Features.RelevantMemory = RelevantMemoryCheck.IsChecked == true;
            settings.Features.AutomaticImages = AutoImagesCheck.IsChecked == true;
            await _api.SaveSettingsAsync(settings);
            AiNameText.Text = string.IsNullOrWhiteSpace(settings.AiName) ? "AI" : settings.AiName;
            await RefreshAisAsync();
            ServerStatus.Text = "Settings saved to AI-Server.";
        }
        catch (Exception ex) { ServerStatus.Text = ex.Message; }
    }

    private async void ChangeAiPhoto_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog { Filter = "Images|*.jpg;*.jpeg;*.png;*.webp;*.gif" };
        if (dialog.ShowDialog() != true) return;
        try
        {
            var url = await _api.UploadAiPhotoAsync(dialog.FileName);
            if (!string.IsNullOrWhiteSpace(url))
            {
                var settings = await _api.GetSettingsAsync();
                settings.ProfilePhoto = url;
                await _api.SaveSettingsAsync(settings);
                await SetAiPhotoAsync(url);
            }
        }
        catch (Exception ex) { ServerStatus.Text = ex.Message; }
    }

    private void Attach_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog { Filter = "Images|*.jpg;*.jpeg;*.png;*.webp;*.gif|All files|*.*" };
        if (dialog.ShowDialog() == true) { _attachedImage = dialog.FileName; ServerStatus.Text = "Attached: " + Path.GetFileName(_attachedImage); }
    }

    private async void MessageBox_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter && Keyboard.Modifiers != ModifierKeys.Shift) { e.Handled = true; await SendMessageAsync(); }
    }

    private async void Send_Click(object sender, RoutedEventArgs e) => await SendMessageAsync();

    private async Task SendMessageAsync()
    {
        var message = MessageBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(message) && string.IsNullOrWhiteSpace(_attachedImage)) return;
        var image = _attachedImage; _attachedImage = null; MessageBox.Clear();
        Messages.Add(new ChatMessage { Role = "You", Text = message });
        EmptyChatText.Visibility = Visibility.Collapsed;
        MessagesList.ScrollIntoView(Messages[^1]);
        try
        {
            ServerStatus.Text = "AI is thinking...";
            var response = await _api.ChatAsync(message, image);
            Messages.Add(new ChatMessage { Role = AiNameText.Text, Text = string.IsNullOrWhiteSpace(response.Reply) ? "No response returned." : response.Reply, Image = response.Image });
            MessagesList.ScrollIntoView(Messages[^1]);
            ServerStatus.Text = "Connected to AI-Server";
        }
        catch (Exception ex)
        {
            Messages.Add(new ChatMessage { Role = "System", Text = "Request failed: " + ex.Message });
            MessagesList.ScrollIntoView(Messages[^1]); ServerStatus.Text = "API error";
        }
    }

    private async Task SetAiPhotoAsync(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) { AiPhoto.Source = null; return; }
        try
        {
            using var client = new HttpClient();
            var bytes = await client.GetByteArrayAsync(_api.ResolveUrl(path));
            using var ms = new MemoryStream(bytes);
            var image = new BitmapImage(); image.BeginInit(); image.CacheOption = BitmapCacheOption.OnLoad; image.StreamSource = ms; image.EndInit(); image.Freeze(); AiPhoto.Source = image;
        }
        catch { AiPhoto.Source = null; }
    }
}
