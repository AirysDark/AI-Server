using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media.Imaging;
using Microsoft.Win32;

namespace AIServerWindows;

public partial class MainWindow : Window
{
    private readonly ApiClient _api = new();
    private string? _attachedImage;
    private bool _changingAi;
    public ObservableCollection<ChatMessage> Messages { get; } = new();

    public MainWindow() { InitializeComponent(); DataContext = this; Loaded += MainWindow_Loaded; }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        try
        {
            var health = await _api.HealthAsync();
            LoginStatus.Text = health.Ok ? $"Connected to {health.Host}" : "Server responded, but health check failed.";
        }
        catch (Exception ex)
        {
            LoginStatus.Text = FormatException("Server unavailable", ex);
        }
    }

    private async void Login_Click(object sender, RoutedEventArgs e) => await Authenticate(() => _api.LoginAsync(EmailBox.Text.Trim(), PasswordBox.Password));
    private async void Register_Click(object sender, RoutedEventArgs e) => await Authenticate(() => _api.RegisterAsync(EmailBox.Text.Trim(), PasswordBox.Password, UsernameBox.Text.Trim()));

    private async Task Authenticate(Func<Task<AuthResponse>> action)
    {
        try
        {
            SetLoginEnabled(false);
            LoginStatus.Text = "Connecting to AI-Server...";
            await action();
            await ShowMainAsync();
        }
        catch (Exception ex)
        {
            LoginStatus.Text = FormatException("Connection failed", ex);
        }
        finally
        {
            SetLoginEnabled(true);
        }
    }

    private static string FormatException(string prefix, Exception ex)
    {
        var lines = new List<string> { prefix + ": " + ex.Message };
        var inner = ex.InnerException;
        while (inner != null)
        {
            lines.Add("Inner: " + inner.Message);
            inner = inner.InnerException;
        }
        return string.Join(Environment.NewLine, lines);
    }

    private void SetLoginEnabled(bool enabled) { EmailBox.IsEnabled = enabled; UsernameBox.IsEnabled = enabled; PasswordBox.IsEnabled = enabled; }
    private async Task ShowMainAsync() { LoginView.Visibility = Visibility.Collapsed; MainView.Visibility = Visibility.Visible; await RefreshAisAsync(); await LoadCurrentAiAsync(); }

    private async Task RefreshAisAsync()
    {
        var ais = await _api.GetAisAsync(); _changingAi = true; AiSelector.ItemsSource = ais;
        var selected = ais.FirstOrDefault(x => x.AiId == _api.ActiveAiId) ?? ais.FirstOrDefault(x => x.Active) ?? ais.FirstOrDefault();
        if (selected is not null) AiSelector.SelectedItem = selected; _changingAi = false;
    }

    private async Task LoadCurrentAiAsync()
    {
        try
        {
            var settings = await _api.GetSettingsAsync();
            AiNameText.Text = string.IsNullOrWhiteSpace(settings.AiName) ? "AI" : settings.AiName;
            SettingName.Text = settings.AiName ?? ""; SelectCombo(SettingAiGender, settings.AiGender); SettingUserName.Text = settings.UserName ?? ""; SelectCombo(SettingUserGender, settings.UserGender); SettingHfToken.Password = settings.HfToken ?? "";
            SettingDescription.Text = settings.Description ?? ""; SettingBackground.Text = settings.Background ?? ""; SettingUserInfo.Text = settings.UserInformation ?? "";
            SettingPersonality.Text = settings.Personality ?? ""; SettingInstructions.Text = settings.Instructions ?? ""; SettingTraits.Text = string.Join(Environment.NewLine, settings.Config.Traits); SettingRules.Text = string.Join(Environment.NewLine, settings.Config.Rules);
            OnlineAiCheck.IsChecked = settings.Features.OnlineAi; LearningCheck.IsChecked = settings.Features.Learning; MemoryCheck.IsChecked = settings.Features.LongTermMemory; RelevantMemoryCheck.IsChecked = settings.Features.RelevantMemory; AutoImagesCheck.IsChecked = settings.Features.AutomaticImages; ProactiveCheck.IsChecked = settings.Proactive.Enabled; ProactiveImagesCheck.IsChecked = settings.Features.ProactiveImages;
            await SetImageAsync(AiPhoto, settings.ProfilePhoto); await SetImageAsync(BannerImage, settings.BannerPhoto); await LoadConversationAsync();
        }
        catch (Exception ex) { ServerStatus.Text = FormatException("Unable to load AI", ex); }
    }

    private static void SelectCombo(ComboBox box, string? value) { foreach (var item in box.Items.OfType<ComboBoxItem>()) if (string.Equals(item.Tag?.ToString(), value ?? "", StringComparison.OrdinalIgnoreCase)) { box.SelectedItem = item; return; } if (box.Items.Count > 0) box.SelectedIndex = 0; }
    private static string ComboValue(ComboBox box) => (box.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "";

    private async Task LoadConversationAsync()
    {
        Messages.Clear(); var history = await _api.GetConversationAsync();
        foreach (var entry in history.Conversation ?? new List<ConversationEntry>()) { if (!string.IsNullOrWhiteSpace(entry.User)) Messages.Add(new ChatMessage { Role = "You", Text = entry.User }); if (!string.IsNullOrWhiteSpace(entry.Ai)) Messages.Add(new ChatMessage { Role = AiNameText.Text, Text = entry.Ai, Image = entry.Image }); }
        EmptyChatText.Visibility = Messages.Count == 0 ? Visibility.Visible : Visibility.Collapsed; if (Messages.Count > 0) MessagesList.ScrollIntoView(Messages[Messages.Count - 1]);
    }

    private async void AiSelector_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_changingAi || AiSelector.SelectedItem is not AiSummary ai || string.IsNullOrWhiteSpace(ai.AiId)) return;
        try { _changingAi = true; await _api.SelectAiAsync(ai.AiId); await LoadCurrentAiAsync(); } catch (Exception ex) { ServerStatus.Text = FormatException("AI selection failed", ex); } finally { _changingAi = false; }
    }
    private async void CreateAi_Click(object sender, RoutedEventArgs e) { try { await _api.CreateAiAsync(); await RefreshAisAsync(); await LoadCurrentAiAsync(); } catch (Exception ex) { ServerStatus.Text = FormatException("Create AI failed", ex); } }
    private async void Logout_Click(object sender, RoutedEventArgs e) { try { await _api.LogoutAsync(); } catch { } Messages.Clear(); MainView.Visibility = Visibility.Collapsed; LoginView.Visibility = Visibility.Visible; LoginStatus.Text = "Logged out."; }
    private void Settings_Click(object sender, RoutedEventArgs e) => SettingsColumn.Width = SettingsColumn.Width.Value == 0 ? new GridLength(360) : new GridLength(0);

    private async void SaveSettings_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var settings = await _api.GetSettingsAsync(); settings.AiName = SettingName.Text.Trim(); settings.AiGender = ComboValue(SettingAiGender); settings.UserName = SettingUserName.Text.Trim(); settings.UserGender = ComboValue(SettingUserGender); settings.HfToken = SettingHfToken.Password;
            settings.Description = SettingDescription.Text; settings.Background = SettingBackground.Text; settings.UserInformation = SettingUserInfo.Text; settings.Personality = SettingPersonality.Text; settings.Instructions = SettingInstructions.Text;
            settings.Config.Traits = SettingTraits.Text.Split('\n').Select(x => x.Trim()).Where(x => x.Length > 0).ToList(); settings.Config.Rules = SettingRules.Text.Split('\n').Select(x => x.Trim()).Where(x => x.Length > 0).ToList();
            settings.Features.OnlineAi = OnlineAiCheck.IsChecked == true; settings.Features.Learning = LearningCheck.IsChecked == true; settings.Features.LongTermMemory = MemoryCheck.IsChecked == true; settings.Features.RelevantMemory = RelevantMemoryCheck.IsChecked == true; settings.Features.AutomaticImages = AutoImagesCheck.IsChecked == true; settings.Features.ProactiveImages = ProactiveImagesCheck.IsChecked == true; settings.Proactive.Enabled = ProactiveCheck.IsChecked == true;
            await _api.SaveSettingsAsync(settings); AiNameText.Text = string.IsNullOrWhiteSpace(settings.AiName) ? "AI" : settings.AiName; await RefreshAisAsync(); await SetImageAsync(BannerImage, settings.BannerPhoto); ServerStatus.Text = "Settings saved to AI-Server.";
        }
        catch (Exception ex) { ServerStatus.Text = FormatException("Settings save failed", ex); }
    }

    private async void ChangeProfilePhoto_Click(object sender, RoutedEventArgs e) { var dialog = ImageDialog(); if (dialog.ShowDialog() != true) return; try { var url = await _api.UploadProfilePhotoAsync(dialog.FileName); await SetImageAsync(AiPhoto, url); await RefreshAisAsync(); ServerStatus.Text = "Profile photo updated."; } catch (Exception ex) { ServerStatus.Text = FormatException("Profile photo failed", ex); } }
    private async void ChangeAiPhoto_Click(object sender, RoutedEventArgs e) { var dialog = ImageDialog(); if (dialog.ShowDialog() != true) return; try { await _api.UploadAiPhotoAsync(dialog.FileName); ServerStatus.Text = "Private AI photo added to the server library."; } catch (Exception ex) { ServerStatus.Text = FormatException("AI photo failed", ex); } }
    private async void ChangeBanner_Click(object sender, RoutedEventArgs e) { var dialog = ImageDialog(); if (dialog.ShowDialog() != true) return; try { ServerStatus.Text = "Processing banner..."; var settings = await _api.GetSettingsAsync(); settings.BannerPhoto = await FileToDataUrlAsync(dialog.FileName); await _api.SaveSettingsAsync(settings); await SetImageAsync(BannerImage, settings.BannerPhoto); ServerStatus.Text = "Banner updated."; } catch (Exception ex) { ServerStatus.Text = FormatException("Banner update failed", ex); } }
    private static OpenFileDialog ImageDialog() => new() { Filter = "Images|*.jpg;*.jpeg;*.png;*.webp;*.gif" };

    private static async Task<string> FileToDataUrlAsync(string path)
    {
        await using var stream = File.OpenRead(path); var bitmap = new BitmapImage(); bitmap.BeginInit(); bitmap.CacheOption = BitmapCacheOption.OnLoad; bitmap.StreamSource = stream; bitmap.EndInit(); bitmap.Freeze();
        var encoder = new JpegBitmapEncoder { QualityLevel = 82 }; encoder.Frames.Add(BitmapFrame.Create(bitmap)); using var output = new MemoryStream(); encoder.Save(output); return "data:image/jpeg;base64," + Convert.ToBase64String(output.ToArray());
    }

    private void Attach_Click(object sender, RoutedEventArgs e) { var dialog = new OpenFileDialog { Filter = "Images|*.jpg;*.jpeg;*.png;*.webp;*.gif|All files|*.*" }; if (dialog.ShowDialog() == true) { _attachedImage = dialog.FileName; ServerStatus.Text = "Attached: " + Path.GetFileName(_attachedImage); } }
    private async void MessageBox_KeyDown(object sender, KeyEventArgs e) { if (e.Key == Key.Enter && Keyboard.Modifiers != ModifierKeys.Shift) { e.Handled = true; await SendMessageAsync(); } }
    private async void Send_Click(object sender, RoutedEventArgs e) => await SendMessageAsync();

    private async Task SendMessageAsync()
    {
        var message = MessageBox.Text.Trim(); if (string.IsNullOrWhiteSpace(message) && string.IsNullOrWhiteSpace(_attachedImage)) return; var image = _attachedImage; _attachedImage = null; MessageBox.Clear();
        Messages.Add(new ChatMessage { Role = "You", Text = message }); EmptyChatText.Visibility = Visibility.Collapsed; MessagesList.ScrollIntoView(Messages[Messages.Count - 1]);
        try { ServerStatus.Text = "AI is thinking..."; var response = await _api.ChatAsync(message, image); Messages.Add(new ChatMessage { Role = AiNameText.Text, Text = string.IsNullOrWhiteSpace(response.Reply) ? "No response returned." : response.Reply, Image = response.Image }); MessagesList.ScrollIntoView(Messages[Messages.Count - 1]); ServerStatus.Text = "Connected to AI-Server"; }
        catch (Exception ex) { Messages.Add(new ChatMessage { Role = "System", Text = FormatException("Request failed", ex) }); MessagesList.ScrollIntoView(Messages[Messages.Count - 1]); ServerStatus.Text = "API error"; }
    }

    private async Task SetImageAsync(Image target, string? source)
    {
        if (string.IsNullOrWhiteSpace(source)) { target.Source = null; return; }
        try
        {
            byte[] bytes;
            if (source.StartsWith("data:", StringComparison.OrdinalIgnoreCase)) bytes = Convert.FromBase64String(source[(source.IndexOf(',') + 1)..]);
            else using (var client = new HttpClient()) bytes = await client.GetByteArrayAsync(_api.ResolveUrl(source));
            using var ms = new MemoryStream(bytes); var image = new BitmapImage(); image.BeginInit(); image.CacheOption = BitmapCacheOption.OnLoad; image.StreamSource = ms; image.EndInit(); image.Freeze(); target.Source = image;
        }
        catch { target.Source = null; }
    }
}
