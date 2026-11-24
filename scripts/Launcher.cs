using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace AccessibleNovelReader
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            string appDir = AppDomain.CurrentDomain.BaseDirectory;
            string targetExe = Path.Combine(appDir, "bin", "Accessible_Novel_Reader.exe");
            if (!File.Exists(targetExe))
            {
                MessageBox.Show("Could not find application files in 'bin' directory.\nPlease make sure the 'bin' folder is present.", "Accessible Novel Reader", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = targetExe;
            psi.WorkingDirectory = appDir;
            psi.UseShellExecute = false;

            if (args != null && args.Length > 0)
            {
                psi.Arguments = string.Join(" ", args);
            }

            try
            {
                Process.Start(psi);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to launch Accessible Novel Reader: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}
