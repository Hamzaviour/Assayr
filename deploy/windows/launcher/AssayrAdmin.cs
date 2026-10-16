// Assayr Admin: a small console launcher for "python -m assayr win ...", with the Assayr icon.
// Built by build.ps1 with the C# 5 compiler that ships with Windows (.NET Framework 4),
// so keep to C# 5 syntax: no string interpolation, no expression-bodied members.
// The manifest asks for administrator rights, so Windows shows the UAC prompt before it starts.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32;

static class AssayrAdmin
{
    [DllImport("kernel32.dll")]
    static extern uint GetConsoleProcessList(uint[] list, uint count);

    static string home;
    static string dataDir;

    static int Main(string[] args)
    {
        Console.Title = "Assayr Admin";
        home = AppDomain.CurrentDomain.BaseDirectory;
        dataDir = FindDataDir();
        // Only this process on the console means Windows opened the window for us
        // (Start menu shortcut or double-click), so keep it open until the person is done.
        bool ownWindow = GetConsoleProcessList(new uint[4], 4) <= 1;

        if (args.Length > 0)
        {
            int code = Run(args);
            if (ownWindow)
            {
                Console.WriteLine();
                Console.Write("Press Enter to close.");
                Console.ReadLine();
            }
            return code;
        }

        Banner();
        Run(new[] { "status" });
        while (true)
        {
            Console.WriteLine();
            Console.ForegroundColor = ConsoleColor.Magenta;
            Console.Write("assayr-admin> ");
            Console.ResetColor();
            string line = Console.ReadLine();
            if (line == null) return 0;
            line = line.Trim();
            if (line.Length == 0) continue;
            if (line == "exit" || line == "quit") return 0;
            if (line == "cls" || line == "clear") { Console.Clear(); Banner(); continue; }
            string[] words = Split(line);
            if (words.Length > 0 && words[0] == "assayr-admin") words = Tail(words);
            if (words.Length == 0) continue;
            if (words[0] == "help") { Help(); continue; }
            Run(words);
        }
    }

    static void Banner()
    {
        Console.ForegroundColor = ConsoleColor.Magenta;
        Console.WriteLine("Assayr Admin");
        Console.ResetColor();
        Console.WriteLine("Program: " + home.TrimEnd('\\'));
        Console.WriteLine("Data:    " + dataDir);
        Console.WriteLine("Type help for the commands, exit to close.");
        Console.WriteLine();
    }

    static void Help()
    {
        Console.WriteLine("  status                     Version, address, services, free disk");
        Console.WriteLine("  start | stop | restart     Start, stop or restart Assayr");
        Console.WriteLine("  logs api                   Show a service's log (api, worker, web, db, clamav)");
        Console.WriteLine("  backup                     Back up the database, evidence files and settings");
        Console.WriteLine("  restore FILE               Replace all data with a backup (takes a safety backup first)");
        Console.WriteLine("  create-admin --email EMAIL Create another administrator");
        Console.WriteLine("  update-signatures PATH     Update the malware signatures");
        Console.WriteLine("  exit                       Close this window");
    }

    static string FindDataDir()
    {
        try
        {
            using (RegistryKey hklm = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64))
            using (RegistryKey key = hklm.OpenSubKey(@"SOFTWARE\Assayr"))
            {
                object value = key == null ? null : key.GetValue("DataDir");
                if (value != null && value.ToString().Length > 0) return value.ToString();
            }
        }
        catch (Exception) { }
        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "Assayr");
    }

    static int Run(string[] words)
    {
        string python = Path.Combine(home, @"python\python.exe");
        if (!File.Exists(python))
        {
            Console.Error.WriteLine("Python is missing from " + python + ". Reinstall Assayr.");
            return 1;
        }
        var parts = new List<string> { "-m", "assayr", "win" };
        parts.AddRange(words);
        parts.Add("--data-dir");
        parts.Add(dataDir);
        var info = new ProcessStartInfo(python, Join(parts));
        info.UseShellExecute = false;
        info.WorkingDirectory = home;
        info.EnvironmentVariables["ASSAYR_HOME"] = home;
        info.EnvironmentVariables["ASSAYR_DATA_DIR"] = dataDir;
        info.EnvironmentVariables["ASSAYR_ENV_FILE"] = Path.Combine(dataDir, "assayr.env");
        info.EnvironmentVariables["PYTHONUTF8"] = "1";
        // Ctrl+C stops the running command (for example a log follow), not this window.
        ConsoleCancelEventHandler keep = (sender, e) => { e.Cancel = true; };
        Console.CancelKeyPress += keep;
        try
        {
            using (Process process = Process.Start(info))
            {
                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("Could not start the command: " + error.Message);
            return 1;
        }
        finally
        {
            Console.CancelKeyPress -= keep;
        }
    }

    static string[] Tail(string[] words)
    {
        var rest = new string[words.Length - 1];
        Array.Copy(words, 1, rest, 0, rest.Length);
        return rest;
    }

    // Splits a typed line into words; double quotes group a path with spaces.
    static string[] Split(string line)
    {
        var words = new List<string>();
        var word = new StringBuilder();
        bool quoted = false, any = false;
        foreach (char c in line)
        {
            if (c == '"') { quoted = !quoted; any = true; }
            else if (char.IsWhiteSpace(c) && !quoted)
            {
                if (any) { words.Add(word.ToString()); word.Clear(); any = false; }
            }
            else { word.Append(c); any = true; }
        }
        if (any) words.Add(word.ToString());
        return words.ToArray();
    }

    // Quotes arguments the way the Windows C runtime parses them back.
    static string Join(List<string> parts)
    {
        var sb = new StringBuilder();
        foreach (string part in parts)
        {
            if (sb.Length > 0) sb.Append(' ');
            if (part.Length > 0 && part.IndexOfAny(new[] { ' ', '\t', '"' }) < 0) { sb.Append(part); continue; }
            sb.Append('"');
            int slashes = 0;
            foreach (char c in part)
            {
                if (c == '\\') { slashes++; continue; }
                if (c == '"') sb.Append('\\', slashes * 2 + 1);
                else sb.Append('\\', slashes);
                slashes = 0;
                sb.Append(c);
            }
            sb.Append('\\', slashes * 2);
            sb.Append('"');
        }
        return sb.ToString();
    }
}
