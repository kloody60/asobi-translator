// مثبّت ومزيل مترجم Asobi. يُبنى بـ build.ps1 (C# 5 / .NET Framework، بدون أي أدوات إضافية).
// الاستخدام: Setup.exe  |  Setup.exe /uninstall  |  /test (يتخطى بايثون والنماذج)  /silent  /dir=PATH  /shot=DIR
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

static class App
{
    public const string Id = "AsobiTranslator";
    public const string Name = "\u0645\u062A\u0631\u062C\u0645 Asobi";
    public static bool Test, Silent, NoLinks;
    public static string Dir, ShotDir;
    public static string Version = "1.0.0";

    [STAThread]
    static void Main(string[] args)
    {
        string def = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", Id);
        Dir = def;
        bool un = Path.GetFileNameWithoutExtension(Application.ExecutablePath).ToLower().StartsWith("uninstall");
        foreach (string a in args)
        {
            if (a == "/uninstall") un = true;
            else if (a == "/test") Test = true;
            else if (a == "/silent") Silent = true;
            else if (a == "/nolinks") NoLinks = true;
            else if (a.StartsWith("/dir=")) Dir = a.Substring(5).Trim('"');
            else if (a.StartsWith("/shot=")) ShotDir = a.Substring(6).Trim('"');
        }
        if (un && !args.Equals(null) && Dir == def)
        {
            string here = Path.GetDirectoryName(Application.ExecutablePath);
            if (File.Exists(Path.Combine(here, "app.py"))) Dir = here;
            else
            {
                try { using (RegistryKey k = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\" + Id)) { if (k != null) Dir = (string)k.GetValue("InstallLocation", Dir); } } catch { }
            }
        }
        try
        {
            using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
            using (ZipArchive z = new ZipArchive(s))
            {
                ZipArchiveEntry e = z.GetEntry("version.py");
                if (e != null)
                {
                    string t = new StreamReader(e.Open()).ReadToEnd();
                    System.Text.RegularExpressions.Match m = System.Text.RegularExpressions.Regex.Match(t, "VERSION\\s*=\\s*\"([^\"]+)\"");
                    if (m.Success) Version = m.Groups[1].Value;
                }
            }
        }
        catch { }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new MainForm(un));
    }
}

// ---------- عناصر واجهة بتصميم مخصص ----------
class Pal
{
    public static Color Bg = ColorTranslator.FromHtml("#0e1120"), Card = ColorTranslator.FromHtml("#171b30"),
        Line = ColorTranslator.FromHtml("#262c4a"), Text = ColorTranslator.FromHtml("#e8eaf6"),
        Muted = ColorTranslator.FromHtml("#8b93b8"), A = ColorTranslator.FromHtml("#6d5dfc"),
        B = ColorTranslator.FromHtml("#16b8f3"), Bad = ColorTranslator.FromHtml("#e5484d");
}

class GButton : Button
{
    public bool Primary = true;
    bool hover;
    public GButton()
    {
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer, true);
        Cursor = Cursors.Hand; Font = new Font("Segoe UI", 11f, FontStyle.Bold); Height = 46;
        MouseEnter += delegate { hover = true; Invalidate(); };
        MouseLeave += delegate { hover = false; Invalidate(); };
    }
    protected override void OnPaint(PaintEventArgs e)
    {
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        e.Graphics.Clear(Parent != null ? Parent.BackColor : Pal.Bg);
        Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
        using (GraphicsPath p = Round(r, 6))
        {
            if (!Enabled) using (Brush b = new SolidBrush(Pal.Card)) e.Graphics.FillPath(b, p);
            else if (Primary) using (Brush b = new LinearGradientBrush(r, hover ? ColorTranslator.FromHtml("#8174ff") : Pal.A, hover ? ColorTranslator.FromHtml("#3cc6f7") : Pal.B, 0f)) e.Graphics.FillPath(b, p);
            else { using (Brush b = new SolidBrush(hover ? ColorTranslator.FromHtml("#2c3460") : ColorTranslator.FromHtml("#232949"))) e.Graphics.FillPath(b, p); using (Pen pn = new Pen(ColorTranslator.FromHtml("#323a63"))) e.Graphics.DrawPath(pn, p); }
        }
        TextRenderer.DrawText(e.Graphics, Text, Font, r, Enabled ? Color.White : Pal.Muted, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.RightToLeft);
    }
    public static GraphicsPath Round(Rectangle r, int d)
    {
        GraphicsPath p = new GraphicsPath(); int x = d * 2;
        p.AddArc(r.X, r.Y, x, x, 180, 90); p.AddArc(r.Right - x, r.Y, x, x, 270, 90);
        p.AddArc(r.Right - x, r.Bottom - x, x, x, 0, 90); p.AddArc(r.X, r.Bottom - x, x, x, 90, 90);
        p.CloseFigure(); return p;
    }
}

class GBar : Control
{
    double v;
    public GBar() { SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.AllPaintingInWmPaint, true); Height = 10; }
    public double Value { get { return v; } set { v = Math.Max(0, Math.Min(1, value)); Invalidate(); } }
    protected override void OnPaint(PaintEventArgs e)
    {
        e.Graphics.Clear(Parent.BackColor); e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
        using (GraphicsPath p = GButton.Round(r, 4)) using (Brush b = new SolidBrush(Pal.Card)) e.Graphics.FillPath(b, p);
        int w = (int)(r.Width * v);
        if (w > 8)
        {
            Rectangle f = new Rectangle(r.Right - w, 0, w, r.Height);  // يمتلئ من اليمين (عربي)
            using (GraphicsPath p = GButton.Round(f, 4)) using (Brush b = new LinearGradientBrush(f, Pal.A, Pal.B, 0f)) e.Graphics.FillPath(b, p);
        }
    }
}

class MainForm : Form
{
    bool uninstall, busy, done;
    Panel pWelcome, pProg, pDone;
    TextBox txtDir; CheckBox cbDesk, cbMenu, cbLaunch, cbKeep;
    GButton btnMain, btnAlt;
    GBar bar; Label lbStep, lbPct, lbDoneT, lbDoneS; TextBox log;
    Point dragFrom; Image logo;
    Thread worker;

    public MainForm(bool un)
    {
        uninstall = un;
        FormBorderStyle = FormBorderStyle.None; StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(720, 520); BackColor = Pal.Bg; ForeColor = Pal.Text; Font = new Font("Segoe UI", 10f);
        Text = App.Name; DoubleBuffered = true;
        try
        {
            Assembly a = Assembly.GetExecutingAssembly();
            using (Stream s = a.GetManifestResourceStream("icon.png")) if (s != null) logo = new Bitmap(s);
            using (Stream s = a.GetManifestResourceStream("icon.ico")) if (s != null) Icon = new Icon(s);
        }
        catch { }
        Region = new Region(GButton.Round(new Rectangle(0, 0, Width, Height), 10));

        MouseDown += delegate (object o, MouseEventArgs e) { dragFrom = e.Location; };
        MouseMove += delegate (object o, MouseEventArgs e) { if (e.Button == MouseButtons.Left) Location = new Point(Location.X + e.X - dragFrom.X, Location.Y + e.Y - dragFrom.Y); };

        Label x = new Label { Text = "\u2715", ForeColor = Pal.Muted, AutoSize = false, Size = new Size(40, 32), Location = new Point(8, 6), TextAlign = ContentAlignment.MiddleCenter, Cursor = Cursors.Hand, Font = new Font("Segoe UI", 11f) };
        x.Click += delegate { if (!busy || MessageBox.Show(Tr("cancel?"), App.Name, MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2, MessageBoxOptions.RtlReading | MessageBoxOptions.RightAlign) == DialogResult.Yes) Environment.Exit(0); };
        x.MouseEnter += delegate { x.ForeColor = Pal.Bad; }; x.MouseLeave += delegate { x.ForeColor = Pal.Muted; };
        Controls.Add(x);

        Label t = L(uninstall ? "\u0625\u0632\u0627\u0644\u0629 " + App.Name : "\u0645\u0631\u062D\u0628\u0627\u064B \u0628\u0643 \u0641\u064A " + App.Name, 22, true, Color.White);
        t.SetBounds(150, 36, 470, 40); Controls.Add(t);
        Label s2 = L(uninstall ? "\u0633\u064A\u062A\u0645 \u062D\u0630\u0641 \u0627\u0644\u0628\u0631\u0646\u0627\u0645\u062C \u0645\u0646 \u062C\u0647\u0627\u0632\u0643" : "\u062A\u0631\u062C\u0645\u0629 \u0641\u0648\u0631\u064A\u0629 \u0644\u0623\u0644\u0639\u0627\u0628 \u0627\u0644\u0631\u064A\u0645\u0648\u062A \u0628\u0644\u0627\u064A  \u2022  \u0627\u0644\u0625\u0635\u062F\u0627\u0631 " + App.Version, 11, false, Pal.Muted);
        s2.RightToLeft = RightToLeft.No; s2.SetBounds(150, 80, 430, 26); Controls.Add(s2);

        BuildWelcome(); BuildProgress(); BuildDone();
        pWelcome.Visible = true;
        Shown += delegate
        {
            if (txtDir != null) { txtDir.SelectionLength = 0; } btnMain.Focus();
            Shot("1-welcome");
            if (App.Silent) btnMain.PerformClick();
        };
    }


    // يكتشف كرت NVIDIA عشان نخبر المستخدم أي نماذج بتنزل
    static string GpuNote()
    {
        string name = null; double gb = 0;
        try
        {
            ProcessStartInfo si = new ProcessStartInfo("nvidia-smi", "--query-gpu=name,memory.total --format=csv,noheader,nounits") { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true };
            using (Process p = Process.Start(si))
            {
                string o = p.StandardOutput.ReadLine(); p.WaitForExit(5000);
                if (o != null) { int i = o.LastIndexOf(','); name = o.Substring(0, i).Trim(); gb = double.Parse(o.Substring(i + 1).Trim(), System.Globalization.CultureInfo.InvariantCulture) / 1024.0; }
            }
        }
        catch { }
        string head = "التثبيت يحتاج إنترنت. ";
        if (name == null) return head + "ما لقيت كرت شاشة NVIDIA، فالبرنامج بيشتغل على المعالج (أبطأ بكثير). حجم التنزيل حوالي 5 جيجا.";
        int dl = gb >= 19.4 ? 22 : gb >= 11.4 ? 20 : gb >= 7.4 ? 10 : 5;
        string lvl = gb >= 19.4 ? "أقصى جودة" : gb >= 11.4 ? "عالية" : gb >= 7.4 ? "متوسطة" : gb >= 3.4 ? "خفيفة" : "معالج فقط";
        return head + "كرتك: " + name + " (" + Math.Round(gb) + " GB).\nالبرنامج يختار تلقائياً نماذج تناسب كرتك (مستوى «" + lvl + "»)، وحجم التنزيل حوالي " + dl + " جيجا.";
    }

    string Tr(string k)
    {
        switch (k)
        {
            case "cancel?": return "\u0627\u0644\u062A\u062B\u0628\u064A\u062A \u0645\u0627\u0632\u0627\u0644 \u0634\u063A\u0627\u0644. \u062A\u0628\u064A \u062A\u0644\u063A\u064A\u0647\u061F";
        }
        return k;
    }

    Label L(string text, float size, bool bold, Color c)
    {
        return new Label { Text = text, Font = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular), ForeColor = c, BackColor = Color.Transparent, RightToLeft = RightToLeft.Yes, TextAlign = ContentAlignment.MiddleRight, AutoSize = false };
    }

    CheckBox CB(string text, bool on, int y)
    {
        CheckBox c = new CheckBox { Text = text, Checked = on, ForeColor = Pal.Text, BackColor = Color.Transparent, RightToLeft = RightToLeft.Yes, Location = new Point(60, y), Size = new Size(600, 28), Cursor = Cursors.Hand };
        return c;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using (Brush b = new LinearGradientBrush(new Rectangle(0, 0, Width, 4), Pal.A, Pal.B, 0f)) e.Graphics.FillRectangle(b, 0, 0, Width, 4);
        if (logo != null) e.Graphics.DrawImage(logo, new Rectangle(Width - 130, 22, 92, 92));
        using (Pen p = new Pen(Pal.Line)) e.Graphics.DrawLine(p, 30, 132, Width - 30, 132);
    }

    void BuildWelcome()
    {
        pWelcome = new Panel { Bounds = new Rectangle(0, 140, 720, 380), BackColor = Pal.Bg, Visible = false }; Controls.Add(pWelcome);
        if (!uninstall)
        {
            Label l = L("\u0645\u0643\u0627\u0646 \u0627\u0644\u062A\u062B\u0628\u064A\u062A", 10, true, Pal.Muted); l.SetBounds(60, 14, 600, 24); pWelcome.Controls.Add(l);
            txtDir = new TextBox { Text = App.Dir, Location = new Point(150, 42), Size = new Size(510, 28), BackColor = Pal.Card, ForeColor = Pal.Text, BorderStyle = BorderStyle.FixedSingle };
            pWelcome.Controls.Add(txtDir);
            GButton br = new GButton { Primary = false, Text = "\u062A\u063A\u064A\u064A\u0631", Bounds = new Rectangle(60, 40, 84, 32), Font = new Font("Segoe UI", 9.5f, FontStyle.Bold) };
            br.Click += delegate { using (FolderBrowserDialog d = new FolderBrowserDialog()) if (d.ShowDialog() == DialogResult.OK) txtDir.Text = Path.Combine(d.SelectedPath, App.Id); };
            pWelcome.Controls.Add(br);
            cbDesk = CB("\u0623\u0636\u0641 \u0627\u062E\u062A\u0635\u0627\u0631\u0627\u064B \u0639\u0644\u0649 \u0633\u0637\u062D \u0627\u0644\u0645\u0643\u062A\u0628", true, 92);
            cbMenu = CB("\u0623\u0636\u0641 \u0627\u062E\u062A\u0635\u0627\u0631\u0627\u064B \u0641\u064A \u0642\u0627\u0626\u0645\u0629 \u0627\u0628\u062F\u0623", true, 124);
            cbLaunch = CB("\u0634\u063A\u0651\u0644 \u0627\u0644\u0628\u0631\u0646\u0627\u0645\u062C \u0628\u0639\u062F \u0627\u0644\u062A\u062B\u0628\u064A\u062A", true, 156);
            pWelcome.Controls.AddRange(new Control[] { cbDesk, cbMenu, cbLaunch });
            Label n = L(GpuNote(), 10, false, Pal.Muted); n.RightToLeft = RightToLeft.Yes;
            n.SetBounds(60, 196, 600, 80); pWelcome.Controls.Add(n);
        }
        else
        {
            Label l = L("\u0647\u0644 \u062A\u0628\u064A \u062A\u0632\u064A\u0644 " + App.Name + " \u0645\u0646 \u062C\u0647\u0627\u0632\u0643\u061F", 12, false, Pal.Text); l.SetBounds(60, 24, 600, 30); pWelcome.Controls.Add(l);
            Label d = L(App.Dir, 9.5f, false, Pal.Muted); d.RightToLeft = RightToLeft.No; d.TextAlign = ContentAlignment.MiddleRight; d.SetBounds(60, 58, 600, 24); pWelcome.Controls.Add(d);
            cbKeep = CB("\u0627\u062D\u062A\u0641\u0638 \u0628\u0627\u0644\u0646\u0645\u0627\u0630\u062C \u0648\u0627\u0644\u0625\u0639\u062F\u0627\u062F\u0627\u062A (\u0623\u0633\u0631\u0639 \u0644\u0648 \u0631\u062C\u0639\u062A \u062B\u0628\u0651\u062A\u062A)", true, 104);
            pWelcome.Controls.Add(cbKeep);
        }
        btnMain = new GButton { Text = uninstall ? "\u0625\u0632\u0627\u0644\u0629" : "\u062A\u062B\u0628\u064A\u062A", Bounds = new Rectangle(440, 304, 220, 48) };
        btnMain.Click += delegate { Begin(); };
        btnAlt = new GButton { Primary = false, Text = "\u0625\u0644\u063A\u0627\u0621", Bounds = new Rectangle(60, 304, 120, 48) };
        btnAlt.Click += delegate { Environment.Exit(0); };
        pWelcome.Controls.Add(btnMain); pWelcome.Controls.Add(btnAlt);
    }

    void BuildProgress()
    {
        pProg = new Panel { Bounds = new Rectangle(0, 140, 720, 380), BackColor = Pal.Bg, Visible = false }; Controls.Add(pProg);
        lbStep = L("", 12, true, Pal.Text); lbStep.SetBounds(60, 20, 530, 30); pProg.Controls.Add(lbStep);
        lbPct = L("0%", 12, true, Pal.B); lbPct.RightToLeft = RightToLeft.No; lbPct.TextAlign = ContentAlignment.MiddleLeft; lbPct.SetBounds(60, 20, 80, 30); pProg.Controls.Add(lbPct);
        bar = new GBar { Bounds = new Rectangle(60, 62, 600, 10) }; pProg.Controls.Add(bar);
        log = new TextBox { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, BackColor = Pal.Card, ForeColor = Pal.Muted, BorderStyle = BorderStyle.None, Font = new Font("Consolas", 8.5f), Bounds = new Rectangle(60, 92, 600, 250) };
        pProg.Controls.Add(log);
    }

    void BuildDone()
    {
        pDone = new Panel { Bounds = new Rectangle(0, 140, 720, 380), BackColor = Pal.Bg, Visible = false }; Controls.Add(pDone);
        lbDoneT = L("", 20, true, Color.White); lbDoneT.SetBounds(60, 60, 600, 40); pDone.Controls.Add(lbDoneT);
        lbDoneS = L("", 11, false, Pal.Muted); lbDoneS.SetBounds(60, 108, 600, 100); pDone.Controls.Add(lbDoneS);
        GButton ok = new GButton { Text = "\u0625\u0646\u0647\u0627\u0621", Bounds = new Rectangle(440, 304, 220, 48) };
        ok.Click += delegate { if (!uninstall && cbLaunch != null && cbLaunch.Checked && !fail) Launch(); Environment.Exit(0); };
        pDone.Controls.Add(ok);
    }

    bool fail;
    void Show(Panel p) { pWelcome.Visible = pProg.Visible = pDone.Visible = false; p.Visible = true; }

    void Shot(string name)
    {
        if (App.ShotDir == null) return;
        try
        {
            Directory.CreateDirectory(App.ShotDir);
            using (Bitmap b = new Bitmap(Width, Height)) { DrawToBitmap(b, new Rectangle(0, 0, Width, Height)); b.Save(Path.Combine(App.ShotDir, name + ".png")); }
        }
        catch { }
    }

    void Begin()
    {
        if (!uninstall) App.Dir = txtDir.Text.Trim();
        Show(pProg); busy = true;
        bool desk = cbDesk != null && cbDesk.Checked && !App.NoLinks, menu = cbMenu != null && cbMenu.Checked && !App.NoLinks, keep = cbKeep != null && cbKeep.Checked;
        worker = new Thread(delegate ()
        {
            string err = null;
            try { if (uninstall) Installer.Uninstall(keep, Ui); else Installer.Install(desk, menu, Ui); }
            catch (Exception ex) { err = ex.Message; Installer.Log("ERROR: " + ex); }
            BeginInvoke((Action)delegate { Finish(err); });
        });
        worker.IsBackground = true; worker.Start();
    }

    DateTime lastShot = DateTime.MinValue;
    void Ui(double frac, string step, string line)
    {
        if (IsDisposed) return;
        BeginInvoke((Action)delegate
        {
            if (frac >= 0) { bar.Value = frac; lbPct.Text = ((int)(frac * 100)) + "%"; }
            if (step != null) lbStep.Text = step;
            if (line != null) { log.AppendText(line + "\r\n"); if (log.TextLength > 60000) log.Text = log.Text.Substring(30000); }
            if ((DateTime.Now - lastShot).TotalSeconds > 2 && frac > 0) { lastShot = DateTime.Now; Shot("2-progress"); }
        });
    }

    void Finish(string err)
    {
        busy = false; fail = err != null;
        Show(pDone);
        if (err != null)
        {
            lbDoneT.ForeColor = Pal.Bad;
            lbDoneT.Text = uninstall ? "\u062A\u0639\u0630\u0631\u062A \u0627\u0644\u0625\u0632\u0627\u0644\u0629" : "\u062A\u0639\u0630\u0631 \u0625\u0643\u0645\u0627\u0644 \u0627\u0644\u062A\u062B\u0628\u064A\u062A";
            lbDoneS.Text = err + "\n\u0627\u0644\u0633\u062C\u0644: " + Path.Combine(App.Dir, "install.log");
        }
        else
        {
            lbDoneT.Text = uninstall ? "\u062A\u0645\u062A \u0627\u0644\u0625\u0632\u0627\u0644\u0629 \u2713" : "\u062A\u0645 \u0627\u0644\u062A\u062B\u0628\u064A\u062A \u2713";
            lbDoneS.Text = uninstall ? "\u0646\u062A\u0645\u0646\u0649 \u0646\u0634\u0648\u0641\u0643 \u0642\u0631\u064A\u0628." : "\u0641\u062A\u062D Asobi \u0648\u0627\u062A\u0635\u0644 \u0628\u0627\u0644\u0628\u0644\u0627\u064A\u0633\u062A\u064A\u0634\u0646\u060C \u0628\u0639\u062F\u064A\u0646 \u0627\u0636\u063A\u0637 \u00AB\u0627\u0628\u062F\u0623 \u0627\u0644\u062A\u0631\u062C\u0645\u0629\u00BB.";
        }
        Shot("3-done");
        if (App.Silent) Environment.Exit(err == null ? 0 : 1);
    }

    void Launch()
    {
        try
        {
            string pyw = Path.Combine(App.Dir, @".venv\Scripts\pythonw.exe");
            if (!File.Exists(pyw)) return;
            ProcessStartInfo p = new ProcessStartInfo(pyw, "app.py") { WorkingDirectory = App.Dir, UseShellExecute = false, CreateNoWindow = true };
            Process.Start(p);
        }
        catch { }
    }
}

delegate void UiCb(double frac, string step, string line);

static class Installer
{
    static StreamWriter lg;
    static UiCb ui;
    static double basePct;

    public static void Log(string s)
    {
        try { if (lg != null) { lg.WriteLine(DateTime.Now.ToString("HH:mm:ss ") + s); lg.Flush(); } } catch { }
    }
    static void Say(double frac, string step, string line)
    {
        if (line != null) Log(line); else if (step != null) Log("== " + step);
        ui(frac, step, line);
    }

    static string Reg { get { return @"Software\Microsoft\Windows\CurrentVersion\Uninstall\" + App.Id; } }

    // يشغّل أمر بدون نافذة ويمرّر مخرجاته للسجل. يرجع كود الخروج.
    static int Run(string exe, string args, string cwd, double from, double to, string step)
    {
        Say(from, step, "> " + exe + " " + args);
        ProcessStartInfo si = new ProcessStartInfo(exe, args) { WorkingDirectory = cwd, UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true, StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8 };
        si.EnvironmentVariables["PYTHONUTF8"] = "1"; si.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        si.EnvironmentVariables["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"; si.EnvironmentVariables["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1";
        Process p = Process.Start(si);
        DateTime last = DateTime.MinValue; double cur = from; int n = 0;
        DataReceivedEventHandler h = delegate (object o, DataReceivedEventArgs e)
        {
            if (string.IsNullOrWhiteSpace(e.Data)) return;
            n++;
            // تقدّم تقريبي: يتحرك ببطء ما بين البداية والنهاية (ما نعرف الحجم الحقيقي)
            cur = from + (to - from) * (1 - 1 / (1 + n / 60.0));
            string line = e.Data.Length > 160 ? e.Data.Substring(0, 160) : e.Data;
            Log(line);
            if ((DateTime.Now - last).TotalMilliseconds > 250) { last = DateTime.Now; ui(cur, null, line); }
        };
        p.OutputDataReceived += h; p.ErrorDataReceived += h;
        p.BeginOutputReadLine(); p.BeginErrorReadLine();
        p.WaitForExit();
        Say(to, null, null);
        return p.ExitCode;
    }

    static string Q(string s) { return "\"" + s + "\""; }

    static string FindPython()
    {
        string[] cands = {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), @"Programs\Python\Python312\python.exe"),
            @"C:\Program Files\Python312\python.exe" };
        try
        {
            ProcessStartInfo si = new ProcessStartInfo("py", "-3.12 -c \"import sys;print(sys.executable)\"") { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
            using (Process p = Process.Start(si)) { string o = p.StandardOutput.ReadToEnd().Trim(); p.WaitForExit(); if (p.ExitCode == 0 && File.Exists(o)) return o; }
        }
        catch { }
        foreach (string c in cands) if (File.Exists(c)) return c;
        return null;
    }

    static void Extract()
    {
        Directory.CreateDirectory(App.Dir);
        using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
        using (ZipArchive z = new ZipArchive(s))
        {
            string root = Path.GetFullPath(App.Dir) + Path.DirectorySeparatorChar;
            foreach (ZipArchiveEntry e in z.Entries)
            {
                if (e.FullName.EndsWith("/")) continue;
                string dst = Path.GetFullPath(Path.Combine(App.Dir, e.FullName));
                if (!dst.StartsWith(root)) throw new Exception("bad zip path");
                string nm = Path.GetFileName(dst);
                if ((nm == "config.json" || nm == "glossary.json") && File.Exists(dst)) continue;  // نحفظ تعديلات المستخدم
                Directory.CreateDirectory(Path.GetDirectoryName(dst));
                using (Stream o = File.Create(dst)) e.Open().CopyTo(o);
            }
        }
    }

    public static void Install(bool desk, bool menu, UiCb cb)
    {
        ui = cb;
        Directory.CreateDirectory(App.Dir);
        lg = new StreamWriter(Path.Combine(App.Dir, "install.log"), true, Encoding.UTF8);
        Log("install " + App.Version + " -> " + App.Dir + (App.Test ? " (test)" : ""));
        // إيقاف نسخة شغّالة لو كان تحديثاً فوق تثبيت قديم
        KillRunning();
        Say(0.01, "\u062C\u0627\u0631\u064A \u0646\u0633\u062E \u0645\u0644\u0641\u0627\u062A \u0627\u0644\u0628\u0631\u0646\u0627\u0645\u062C...", null);
        Extract();
        File.Copy(Application.ExecutablePath, Path.Combine(App.Dir, "Uninstall.exe"), true);
        string py = Path.Combine(App.Dir, @".venv\Scripts\python.exe");
        if (!App.Test)
        {
            string sys = FindPython();
            if (sys == null)
            {
                Say(0.04, "\u062C\u0627\u0631\u064A \u062A\u0646\u0632\u064A\u0644 Python 3.12...", null);
                int rc = Run("winget", "install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements", App.Dir, 0.04, 0.10, "\u062C\u0627\u0631\u064A \u062A\u0646\u0632\u064A\u0644 Python 3.12...");
                sys = FindPython();
                if (sys == null) throw new Exception("\u0645\u0627 \u0642\u062F\u0631\u062A \u0623\u062B\u0628\u0651\u062A Python 3.12 \u062A\u0644\u0642\u0627\u0626\u064A\u0627\u064B. \u062B\u0628\u0651\u062A\u0647 \u0645\u0646 python.org \u0648\u0634\u063A\u0651\u0644 \u0627\u0644\u0645\u062B\u0628\u0651\u062A \u0645\u0631\u0629 \u062B\u0627\u0646\u064A\u0629.");
            }
            if (!File.Exists(py))
                if (Run(sys, "-m venv .venv", App.Dir, 0.10, 0.14, "\u062C\u0627\u0631\u064A \u0625\u0646\u0634\u0627\u0621 \u0628\u064A\u0626\u0629 \u0627\u0644\u062A\u0634\u063A\u064A\u0644...") != 0) throw new Exception("venv failed");
            Req(Run(py, "-m pip install --upgrade pip", App.Dir, 0.14, 0.16, "\u062C\u0627\u0631\u064A \u062A\u062D\u062F\u064A\u062B pip..."), "pip");
            Req(Run(py, "-m pip install torch --index-url https://download.pytorch.org/whl/cu124", App.Dir, 0.16, 0.40, "\u062C\u0627\u0631\u064A \u062A\u0646\u0632\u064A\u0644 PyTorch (\u0643\u0628\u064A\u0631\u060C \u0635\u0628\u0631 \u0634\u0648\u064A)..."), "torch");
            Req(Run(py, "-m pip install -r requirements.txt", App.Dir, 0.40, 0.55, "\u062C\u0627\u0631\u064A \u062A\u0646\u0632\u064A\u0644 \u0645\u0643\u062A\u0628\u0627\u062A \u0627\u0644\u0628\u0631\u0646\u0627\u0645\u062C..."), "requirements");
                        Req(Run(py, "-m pip install \"transformers[torch]\"", App.Dir, 0.55, 0.58, "جاري تجهيز أداة تحويل النماذج..."), "transformers");
            Req(Run(py, "-u prepare_models.py auto", App.Dir, 0.58, 0.96, "جاري تنزيل نماذج الترجمة والسماع المناسبة لكرتك (أكبر خطوة)..."), "models");
        }
        Say(0.97, "\u062C\u0627\u0631\u064A \u0625\u0646\u0634\u0627\u0621 \u0627\u0644\u0627\u062E\u062A\u0635\u0627\u0631\u0627\u062A...", null);
        string pyw = Path.Combine(App.Dir, @".venv\Scripts\pythonw.exe");
        string target = File.Exists(pyw) ? pyw : Path.Combine(App.Dir, "run.bat");
        string ico = Path.Combine(App.Dir, @"assets\icon.ico");
        string lnkName = App.Name + ".lnk";
        if (desk) Shortcut(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), lnkName), target, "app.py", ico);
        if (menu)
        {
            string d = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), App.Name);
            Directory.CreateDirectory(d);
            Shortcut(Path.Combine(d, lnkName), target, "app.py", ico);
            Shortcut(Path.Combine(d, "\u0625\u0632\u0627\u0644\u0629 " + App.Name + ".lnk"), Path.Combine(App.Dir, "Uninstall.exe"), "", ico);
        }
        using (RegistryKey k = Registry.CurrentUser.CreateSubKey(Reg))
        {
            k.SetValue("DisplayName", App.Name); k.SetValue("DisplayVersion", App.Version); k.SetValue("Publisher", "Asobi Translator");
            k.SetValue("InstallLocation", App.Dir); k.SetValue("DisplayIcon", ico);
            k.SetValue("UninstallString", Q(Path.Combine(App.Dir, "Uninstall.exe")) + " /uninstall");
            k.SetValue("NoModify", 1, RegistryValueKind.DWord); k.SetValue("NoRepair", 1, RegistryValueKind.DWord);
        }
        Say(1.0, "\u062A\u0645", "done");
        lg.Close();
    }

    static void Req(int rc, string what) { if (rc != 0) throw new Exception("\u0641\u0634\u0644 \u062E\u0637\u0648\u0629: " + what + " (\u0643\u0648\u062F " + rc + ")"); }

    static void Shortcut(string path, string target, string args, string icon)
    {
        Type t = Type.GetTypeFromProgID("WScript.Shell");
        object sh = Activator.CreateInstance(t);
        object lnk = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, sh, new object[] { path });
        Type lt = lnk.GetType();
        lt.InvokeMember("TargetPath", BindingFlags.SetProperty, null, lnk, new object[] { target });
        lt.InvokeMember("Arguments", BindingFlags.SetProperty, null, lnk, new object[] { args });
        lt.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, lnk, new object[] { App.Dir });
        if (File.Exists(icon)) lt.InvokeMember("IconLocation", BindingFlags.SetProperty, null, lnk, new object[] { icon });
        lt.InvokeMember("Description", BindingFlags.SetProperty, null, lnk, new object[] { App.Name });
        lt.InvokeMember("Save", BindingFlags.InvokeMethod, null, lnk, null);
        Log("shortcut " + path);
    }

    static void KillRunning()
    {
        try
        {
            string venv = Path.GetFullPath(Path.Combine(App.Dir, ".venv")).ToLower();
            foreach (Process p in Process.GetProcessesByName("pythonw"))
            {
                try { if (p.MainModule.FileName.ToLower().StartsWith(venv)) { p.Kill(); p.WaitForExit(3000); } } catch { }
            }
        }
        catch { }
    }

    public static void Uninstall(bool keep, UiCb cb)
    {
        ui = cb;
        Say(0.05, "\u062C\u0627\u0631\u064A \u0625\u064A\u0642\u0627\u0641 \u0627\u0644\u0628\u0631\u0646\u0627\u0645\u062C...", null);
        KillRunning();
        Say(0.25, "\u062C\u0627\u0631\u064A \u062D\u0630\u0641 \u0627\u0644\u0627\u062E\u062A\u0635\u0627\u0631\u0627\u062A...", null);
        string lnkName = App.Name + ".lnk";
        try { File.Delete(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), lnkName)); } catch { }
        try { Directory.Delete(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), App.Name), true); } catch { }
        try { Registry.CurrentUser.DeleteSubKey(Reg, false); } catch { }
        Say(0.5, "\u062C\u0627\u0631\u064A \u062D\u0630\u0641 \u0645\u0644\u0641\u0627\u062A \u0627\u0644\u0628\u0631\u0646\u0627\u0645\u062C...", null);
        string self = Path.GetFullPath(Application.ExecutablePath).ToLower();
        string dir = Path.GetFullPath(App.Dir);
        if (!File.Exists(Path.Combine(dir, "app.py"))) throw new Exception("\u0645\u062C\u0644\u062F \u0627\u0644\u062A\u062B\u0628\u064A\u062A \u0645\u0648 \u0645\u0639\u0631\u0648\u0641");
        List<string> rm = new List<string>();
        foreach (string e in Directory.GetFileSystemEntries(dir))
        {
            string n = Path.GetFileName(e).ToLower();
            if (keep && (n == "models" || n == "config.json" || n == "glossary.json")) continue;
            if (e.ToLower() == self) continue;
            rm.Add(e);
        }
        foreach (string e in rm)
        {
            try { if (Directory.Exists(e)) Directory.Delete(e, true); else File.Delete(e); }
            catch (Exception ex) { Log("skip " + e + ": " + ex.Message); }
        }
        // الملف التنفيذي نفسه يُحذف بعد ما نقفل (cmd مخفي)
        string tgt = keep ? Q(self) : Q(dir);
        string cmd = keep ? "/c ping 127.0.0.1 -n 3 >nul & del /f /q " + tgt : "/c ping 127.0.0.1 -n 3 >nul & rmdir /s /q " + tgt;
        Process.Start(new ProcessStartInfo("cmd.exe", cmd) { CreateNoWindow = true, UseShellExecute = false, WindowStyle = ProcessWindowStyle.Hidden });
        Say(1.0, "\u062A\u0645", null);
    }
}
