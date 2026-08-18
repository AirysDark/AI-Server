using System;
using System.Windows;

namespace AIServerWindows;

public partial class MainWindow
{
    private async void DeleteAi_Click(object sender, RoutedEventArgs e)
    {
        if (AiSelector.SelectedItem is not AiSummary ai || string.IsNullOrWhiteSpace(ai.AiId))
        {
            ServerStatus.Text = "Select an AI to delete.";
            return;
        }

        var name = string.IsNullOrWhiteSpace(ai.AiName) ? "this AI" : $"\"{ai.AiName}\"";
        var answer = System.Windows.MessageBox.Show(
            $"Delete {name}?\n\nThis permanently removes the AI and its server-side data. This cannot be undone.",
            "Delete AI",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning,
            MessageBoxResult.No);

        if (answer != MessageBoxResult.Yes)
            return;

        try
        {
            ServerStatus.Text = "Deleting AI...";
            await _api.DeleteAiAsync(ai.AiId);
            _api.ActiveAiId = null;
            await RefreshAisAsync();
            await LoadCurrentAiAsync();
            ServerStatus.Text = $"Deleted {name}.";
        }
        catch (Exception ex)
        {
            ServerStatus.Text = FormatException("Delete AI failed", ex);
        }
    }
}
