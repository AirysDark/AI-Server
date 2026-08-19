using System.Windows;
using System.Windows.Input;
namespace AiServer.Companion;
public partial class MainWindow : Window
{
    public MainWindow(){InitializeComponent();}
    private void Window_Loaded(object sender, RoutedEventArgs e)
    {
        var area=SystemParameters.WorkArea;
        Left=area.Left+12;
        Top=area.Bottom-Height-12;
    }
    private void Send_Click(object sender,RoutedEventArgs e)=>SendMessage();
    private void MessageInput_KeyDown(object sender,KeyEventArgs e){if(e.Key==Key.Enter){SendMessage();e.Handled=true;}}
    private void SendMessage(){var text=MessageInput.Text.Trim();if(text.Length==0)return;ChatText.Text+=(ChatText.Text.Length>0?"\n\n":"")+"You: "+text;MessageInput.Clear();}
    private void Close_Click(object sender,RoutedEventArgs e)=>Hide();
}
