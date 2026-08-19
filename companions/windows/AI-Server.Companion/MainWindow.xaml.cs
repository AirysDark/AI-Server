using System.Windows;
using System.Windows.Input;

namespace AiServer.Companion;

public partial class MainWindow : Window
{
    private readonly CompanionClient _client = new();

    public MainWindow()
    {
        InitializeComponent();
        _client.MessageReceived += OnMessageReceived;
        _client.ConnectionChanged += OnConnectionChanged;
    }

    private async void Window_Loaded(object sender, RoutedEventArgs e)
    {
        var area = SystemParameters.WorkArea;
        Left = area.Left + 12;
        Top = area.Bottom - Height - 12;
        await _client.ConnectAsync();
        _ = _client.StartLiveAsync();
    }

    private void OnConnectionChanged(bool connected)
    {
        Dispatcher.Invoke(() => TypingText.Text = connected ? "" : "Disconnected — reconnecting…");
    }

    private void OnMessageReceived(string name, string text)
    {
        Dispatcher.Invoke(() =>
        {
            AiNameText.Text = name;
            ChatText.Text += (ChatText.Text.Length > 0 ? "\n\n" : "") + name + ": " + text;
            TypingText.Text = "";
            Show();
            Activate();
        });
    }

    private async void Send_Click(object sender, RoutedEventArgs e) => await SendMessageAsync();

    private async void MessageInput_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            e.Handled = true;
            await SendMessageAsync();
        }
    }

    private async Task SendMessageAsync()
    {
        var text = MessageInput.Text.Trim();
        if (text.Length == 0) return;
        ChatText.Text += (ChatText.Text.Length > 0 ? "\n\n" : "") + "You: " + text;
        MessageInput.Clear();
        TypingText.Text = "AI is typing…";
        try { await _client.SendAsync(text); }
        catch { TypingText.Text = "Unable to send — check connection."; }
    }

    private void Close_Click(object sender, RoutedEventArgs e) => Hide();
}
