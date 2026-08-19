using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media.Imaging;

namespace AiServer.Companion;

public partial class MainWindow : Window
{
    private readonly CompanionClient _client = new();
    private bool _registerMode;
    private bool _loadingAi;

    public MainWindow()
    {
        InitializeComponent();
        _client.MessageReceived += OnMessageReceived;
        _client.ConnectionChanged += OnConnectionChanged;
    }

    private async void Window_Loaded(object sender, RoutedEventArgs e)
    {
        PositionWindow();
        ShowLogin("Sign in to your AI Server account.");
        try { await _client.ConnectAsync(); ConnectionText.Text = "  • Server online"; }
        catch { ConnectionText.Text = "  • Offline"; }
    }

    private void PositionWindow() { var area = SystemParameters.WorkArea; Left = area.Left + 14; Top = area.Bottom - Height - 14; }
    private void TitleBar_MouseDown(object sender, MouseButtonEventArgs e) { if (e.LeftButton == MouseButtonState.Pressed) DragMove(); }

    private async void Login_Click(object sender, RoutedEventArgs e)
    {
        try { SetAuthEnabled(false); LoginStatus.Text = "Signing in…"; await _client.LoginAsync(EmailBox.Text.Trim(), PasswordBox.Password); await ShowMainAsync(); }
        catch (Exception ex) { LoginStatus.Text = ex.Message; }
        finally { SetAuthEnabled(true); }
    }

    private async void Register_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(UsernameBox.Text)) { LoginStatus.Text = "Enter a username to register."; return; }
            SetAuthEnabled(false); LoginStatus.Text = "Creating account…"; await _client.RegisterAsync(EmailBox.Text.Trim(), PasswordBox.Password, UsernameBox.Text.Trim()); await ShowMainAsync();
        }
        catch (Exception ex) { LoginStatus.Text = ex.Message; }
        finally { SetAuthEnabled(true); }
    }

    private void ToggleRegister_Click(object sender, RoutedEventArgs e)
    {
        _registerMode = !_registerMode; UsernameBox.Visibility = _registerMode ? Visibility.Visible : Visibility.Collapsed; LoginButton.Visibility = _registerMode ? Visibility.Collapsed : Visibility.Visible; RegisterButton.Visibility = Visibility.Visible; ToggleRegisterButton.Content = _registerMode ? "Back to login" : "Create a new account";
    }

    private void SetAuthEnabled(bool enabled) { EmailBox.IsEnabled = enabled; PasswordBox.IsEnabled = enabled; UsernameBox.IsEnabled = enabled; LoginButton.IsEnabled = enabled; RegisterButton.IsEnabled = enabled; }
    private void ShowLogin(string status) { MainView.Visibility = Visibility.Collapsed; LoginView.Visibility = Visibility.Visible; ConnectionText.Text = "  • Offline"; LoginStatus.Text = status; }

    private async Task ShowMainAsync()
    {
        LoginView.Visibility = Visibility.Collapsed; MainView.Visibility = Visibility.Visible; ConnectionText.Text = "  • Connected"; await RefreshAisAsync(); _ = _client.StartLiveAsync(); MessageInput.Focus();
    }

    private async Task RefreshAisAsync()
    {
        _loadingAi = true;
        try
        {
            var ais = await _client.GetAisAsync(); AiSelector.ItemsSource = ais;
            var selected = ais.FirstOrDefault(x => x.AiId == _client.ActiveAiId) ?? ais.FirstOrDefault(x => x.Active) ?? ais.FirstOrDefault();
            if (selected != null)
            {
                AiSelector.SelectedValuePath = nameof(AiChoice.AiId); AiSelector.SelectedValue = selected.AiId; AiNameText.Text = selected.AiName; await LoadAiPhotoAsync(selected.ProfilePhoto);
                if (selected.AiId != _client.ActiveAiId) await _client.SelectAiAsync(selected.AiId);
            }
        }
        catch (Exception ex) { LoginStatus.Text = ex.Message; }
        finally { _loadingAi = false; }
    }

    private async void AiSelector_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_loadingAi || AiSelector.SelectedItem is not AiChoice ai) return;
        try { TypingText.Text = "Switching AI…"; await _client.SelectAiAsync(ai.AiId); AiNameText.Text = ai.AiName; await LoadAiPhotoAsync(ai.ProfilePhoto); TypingText.Text = ""; }
        catch (Exception ex) { TypingText.Text = ex.Message; }
    }

    private async Task LoadAiPhotoAsync(string? path)
    {
        AiPhotoImage.Source = null; FloatingPhotoImage.Source = null;
        var bytes = await _client.GetImageAsync(path);
        if (bytes == null || bytes.Length == 0) return;
        try
        {
            using var stream = new MemoryStream(bytes);
            var image = new BitmapImage(); image.BeginInit(); image.CacheOption = BitmapCacheOption.OnLoad; image.StreamSource = stream; image.EndInit(); image.Freeze();
            AiPhotoImage.Source = image; FloatingPhotoImage.Source = image;
        }
        catch { }
    }

    private void OnConnectionChanged(bool connected) { Dispatcher.Invoke(() => ConnectionText.Text = connected ? "  • Connected" : "  • Reconnecting…"); }

    private async void OnMessageReceived(string name, string text)
    {
        AiNameText.Text = name; ChatText.Text += (ChatText.Text.Length > 0 ? "\n\n" : "") + name + ":\n" + text; TypingText.Text = ""; Show(); Activate(); FloatingButton.Visibility = Visibility.Visible; FloatingButton.ToolTip = name + " wants to talk";
        await LoadAiPhotoAsync(_client.ActiveAiPhoto);
    }

    private void FloatingButton_Click(object sender, RoutedEventArgs e) { FloatingButton.Visibility = Visibility.Collapsed; Show(); Activate(); MessageInput.Focus(); }
    private async void Send_Click(object sender, RoutedEventArgs e) => await SendMessageAsync();
    private async void MessageInput_KeyDown(object sender, KeyEventArgs e) { if (e.Key == Key.Enter && Keyboard.Modifiers != ModifierKeys.Shift) { e.Handled = true; await SendMessageAsync(); } }

    private async Task SendMessageAsync()
    {
        var text = MessageInput.Text.Trim(); if (text.Length == 0) return; ChatText.Text += (ChatText.Text.Length > 0 ? "\n\n" : "") + "You:\n" + text; MessageInput.Clear(); TypingText.Text = (_client.ActiveAiName ?? "AI") + " is typing…";
        try { await _client.SendAsync(text); } catch (Exception ex) { TypingText.Text = ex.Message; }
    }

    private void Minimize_Click(object sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;
    private void Close_Click(object sender, RoutedEventArgs e) { _client.StopLive(); Hide(); }
}
