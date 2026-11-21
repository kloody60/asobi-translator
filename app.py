"""مترجم ألعاب الريموت بلاي: لوحة تحكم + نافذة ترجمة تتحرك وتتلوّن + تحديد منطقة قراءة الشاشة."""
import copy
import ctypes
import html
import ctypes.wintypes as wt
import os
import sys
import threading

from PySide6 import QtCore, QtGui, QtWidgets

import engine as T
import profiles
import updater
from version import APP_NAME, REPO_URL, VERSION

CFG = T.CFG
ICON = T.BASE / "assets" / "icon.png"
CHECK = (T.BASE / "assets" / "check.png").as_posix()

QSS = """
* { font-family: "Segoe UI", "Tahoma"; font-size: 13px; color: #e8eaf6; }
QWidget#root, QScrollArea, QScrollArea > QWidget > QWidget { background: #0e1120; }
QScrollArea { border: none; }
QGroupBox { background: #171b30; border: 1px solid #262c4a; border-radius: 6px; margin-top: 22px; padding: 10px 12px 12px 12px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top right; right: 16px; padding: 0 8px; color: #9aa6ff; font-weight: 700; font-size: 14px; }
QLabel { background: transparent; }
QFrame#side { background: #0a0d1a; border-left: 1px solid #1c2140; }
QPushButton#nav { background: transparent; border: none; border-right: 3px solid transparent; border-radius: 0; text-align: right; padding: 12px 16px; font-size: 14px; color: #aab2d8; }
QPushButton#nav:hover { background: #141830; color: white; }
QPushButton#nav:checked { background: #1a2044; color: white; border-right: 3px solid #6d5dfc; }
QCheckBox#advsw { margin: 8px 16px; color: #8b93b8; }
QFrame#tile { background: #171b30; border: 1px solid #262c4a; border-radius: 6px; }
QLabel#tt { color: #8b93b8; font-size: 12px; }
QLabel#tv { font-size: 15px; font-weight: 700; color: #ffffff; }
QLabel#h1 { font-size: 24px; font-weight: 800; color: #ffffff; }
QLabel#muted { color: #8b93b8; }
QLabel#title { font-size: 22px; font-weight: 800; color: #ffffff; }
QLabel#ver { color: #8b93b8; font-size: 12px; }
QPushButton { background: #232949; border: 1px solid #323a63; border-radius: 4px; padding: 7px 12px; }
QPushButton:hover { background: #2c3460; border-color: #6d5dfc; }
QPushButton:pressed { background: #1d2342; }
QPushButton:checked { background: #6d5dfc; border-color: #8f83ff; color: white; }
QPushButton:disabled { color: #5d6485; background: #1a1f38; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6d5dfc, stop:1 #16b8f3); border: none; color: white; font-weight: 700; }
QPushButton#primary:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #8174ff, stop:1 #3cc6f7); }
QCheckBox { spacing: 8px; padding: 2px 0; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 3px; border: 1px solid #3a4272; background: #10142a; }
QCheckBox::indicator:hover { border-color: #6d5dfc; }
QCheckBox::indicator:checked { background: #6d5dfc; border-color: #8f83ff; image: url(CHECK); }
QComboBox, QDoubleSpinBox, QLineEdit, QFontComboBox { background: #10142a; border: 1px solid #323a63; border-radius: 4px; padding: 5px 8px; selection-background-color: #6d5dfc; }
QComboBox:hover, QDoubleSpinBox:hover, QLineEdit:focus { border-color: #6d5dfc; }
QComboBox QAbstractItemView { background: #171b30; border: 1px solid #323a63; selection-background-color: #6d5dfc; }
QSlider::groove:horizontal { height: 6px; background: #262c4a; border-radius: 3px; }
QSlider::sub-page:horizontal { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6d5dfc, stop:1 #16b8f3); border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; background: #ffffff; border: 2px solid #6d5dfc; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #323a63; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #6d5dfc; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { background: #10142a; border: none; border-radius: 6px; height: 10px; text-align: center; color: transparent; }
QProgressBar::chunk { border-radius: 6px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6d5dfc, stop:1 #16b8f3); }
QToolTip { background: #171b30; color: #e8eaf6; border: 1px solid #6d5dfc; }
"""
u32 = ctypes.windll.user32
u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
u32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
u32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
u32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
u32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
u32.SetForegroundWindow.argtypes = [wt.HWND]

WS_EX_TRANSPARENT, WS_EX_NOACTIVATE = 0x20, 0x08000000
SAMPLE = "هذا نص تجريبي للترجمة"
SAMPLE_EDIT = "اسحب المربع للتحريك • الزاوية = حجم الخط • الحافة اليمين/اليسار = مطّ وتكبير الحروف • الحافة فوق/تحت = ارتفاع"


def exclude_from_capture(w):
    """نستثني نافذتنا من الالتقاط حتى ما يقرا OCR الترجمة نفسها."""
    if os.environ.get("ASOBI_NO_EXCLUDE"):  # للاختبار فقط
        return
    u32.SetWindowDisplayAffinity(wt.HWND(int(w.winId())), 0x11)


def set_affinity(w, exclude):
    u32.SetWindowDisplayAffinity(wt.HWND(int(w.winId())), 0x11 if exclude else 0)


def set_toolwindow(w, on):
    """نافذة أدوات = ما تظهر بشريط المهام ولا بقائمة نوافذ OBS. نطفيها عشان OBS يقدر يضيف الترجمة كمصدر مستقل."""
    h = wt.HWND(int(w.winId()))
    ex = u32.GetWindowLongPtrW(h, -20)
    ex = ((ex | 0x80) & ~0x40000) if on else ((ex & ~0x80) | 0x40000)
    u32.SetWindowLongPtrW(h, -20, ex)


def set_click_through(w, on):
    h = wt.HWND(int(w.winId()))
    ex = u32.GetWindowLongPtrW(h, -20)
    ex = (ex | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE) if on else ((ex & ~WS_EX_TRANSPARENT) | WS_EX_NOACTIVATE)
    u32.SetWindowLongPtrW(h, -20, ex)


def area_rect(widget):
    """مستطيل Asobi بالبكسل الحقيقي، وإذا مو مفتوح نستخدم الشاشة الرئيسية."""
    win = T.find_window()
    if win:
        return win[1:5], True
    scr = QtGui.QGuiApplication.primaryScreen()
    g, dpr = scr.geometry(), scr.devicePixelRatio()
    return (0, 0, int(g.width() * dpr), int(g.height() * dpr)), False


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Toggle(QtWidgets.QCheckBox):
    """صف بمفتاح تشغيل/إيقاف (سويتش) بدل الخانة المربعة، مع خط فاصل بين الصفوف."""

    def __init__(self, text=""):
        super().__init__(text)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAttribute(QtCore.Qt.WA_Hover)
        self.setMinimumHeight(46)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def sizeHint(self):
        return QtCore.QSize(self.fontMetrics().horizontalAdvance(self.text()) + 90, 46)

    def minimumSizeHint(self):
        return QtCore.QSize(120, 46)

    def hitButton(self, pos):
        return self.rect().contains(pos)  # الصف كله قابل للضغط

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if self.underMouse():
            p.fillRect(self.rect(), QtGui.QColor(255, 255, 255, 10))
        p.setPen(QtGui.QColor("#e8eaf6" if self.isEnabled() else "#5d6485"))
        p.setFont(self.font())
        sw_w, sw_h = 46, 26
        p.drawText(QtCore.QRectF(sw_w + 28, 0, w - sw_w - 36, h),
                   QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter | QtCore.Qt.TextWordWrap, self.text())
        track = QtCore.QRectF(10, (h - sw_h) / 2, sw_w, sw_h)
        on = self.isChecked()
        p.setPen(QtCore.Qt.NoPen)
        if on:
            g = QtGui.QLinearGradient(track.left(), 0, track.right(), 0)
            g.setColorAt(0, QtGui.QColor("#6d5dfc"))
            g.setColorAt(1, QtGui.QColor("#4f8cff"))
            p.setBrush(g)
        else:
            p.setBrush(QtGui.QColor("#3a4272"))
        p.drawRoundedRect(track, sw_h / 2, sw_h / 2)
        kx = track.right() - sw_h + 3 if on else track.left() + 3
        p.setBrush(QtGui.QColor("#ffffff"))
        p.drawEllipse(QtCore.QRectF(kx, track.top() + 3, sw_h - 6, sw_h - 6))
        p.setPen(QtGui.QColor("#232949"))
        p.drawLine(0, h - 1, w, h - 1)


class Grip(QtWidgets.QWidget):
    """مقابض الزوايا (تظهر فقط أثناء تحريك الترجمة). ما تستقبل الماوس."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 2))
        p.setBrush(QtGui.QColor("#00d0ff"))
        r, w, h = 8, self.width(), self.height()
        for x, y in ((r + 1, r + 1), (w - r - 2, r + 1), (r + 1, h - r - 2), (w - r - 2, h - r - 2)):
            p.drawEllipse(QtCore.QPoint(x, y), r, r)
        p.setBrush(QtGui.QColor("#ffffff"))
        p.setPen(QtGui.QPen(QtGui.QColor("#00d0ff"), 2))
        for x, y in ((w // 2, 6), (w // 2, h - 7), (6, h // 2), (w - 7, h // 2)):
            p.drawRoundedRect(QtCore.QRectF(x - 7, y - 5, 14, 10) if y in (6, h - 7) else QtCore.QRectF(x - 5, y - 7, 10, 14), 2, 2)


MODES = [("الترجمة العربية", "translate"), ("الكلام الأصلي بدون ترجمة", "original"), ("الاثنين معاً (الأصلي فوق الترجمة)", "both")]


CORNER = 30  # منطقة الزاوية بالبكسل
EDGE = 18    # منطقة الحافة بالبكسل


class Overlay(QtWidgets.QWidget):
    _rs = None
    show_text = QtCore.Signal(str, float)
    placed = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.label = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter, wordWrap=True)
        self.label.setLayoutDirection(QtCore.Qt.RightToLeft)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.label)
        self.edit = False
        self.sample = False
        self._drag = None
        self.timer = QtCore.QTimer(singleShot=True)
        self.timer.timeout.connect(self._expire)
        self.show_text.connect(self._show)
        self.setWindowTitle("Asobi Translation Overlay")
        self.apply_style()
        self.show()
        self.apply_capture()
        set_click_through(self, True)
        self.hide()

    def apply_capture(self):
        """ظاهرة للبث والتسجيل (افتراضي) أو مخفية عنهم، ووضع OBS (نافذة مستقلة)."""
        o = CFG["overlay"]
        set_affinity(self, (not o["visible_in_capture"]) and not os.environ.get("ASOBI_NO_EXCLUDE"))
        set_toolwindow(self, not o["obs_window"])
        if self.isVisible():
            self.hide()
            self.show()  # عشان ويندوز يحدّث شريط المهام

    # --- المظهر ---
    def font_scale(self):
        """الخط يتناسب مع ارتفاع نافذة Asobi (أو الشاشة): الحجم المحفوظ يمثّل شاشة 1080p."""
        try:
            (l, t, r, b), _ = area_rect(self)
            return clamp((b - t) / self.devicePixelRatioF() / 1080.0, 0.6, 3.0)
        except Exception:
            return 1.0

    def apply_style(self):
        o = CFG["overlay"]
        pt = o["font_size"] * self.font_scale()
        tc, bc = QtGui.QColor(o["text_color"]), QtGui.QColor(o["bg_color"])
        tc.setAlpha(int(o["text_opacity"] * 2.55))
        bc.setAlpha(int(o["bg_opacity"] * 2.55))
        # الخط يُحدَّد في الستايل نفسه: الستايل العام للتطبيق (font-size: 13px) كان يغطي على setFont
        css = (f"color:rgba({tc.red()},{tc.green()},{tc.blue()},{tc.alpha()});"
               f"background:rgba({bc.red()},{bc.green()},{bc.blue()},{bc.alpha()});"
               f"font-family:'{o['font']}';font-size:{pt:.1f}pt;font-weight:700;"
               f"padding:{int(o.get('pad_y', 10))}px 22px;border-radius:{int(o['radius'])}px;")
        if self.edit:
            css += "border:3px dashed #00d0ff;"
        self.label.setStyleSheet(css)

    def place(self, allow_fallback=False):
        (l, t, r, b), real = area_rect(self)
        if not real and not allow_fallback:
            return False
        o = CFG["overlay"]
        w, h = r - l, b - t
        dpr = self.devicePixelRatioF()
        self.label.setFixedWidth(max(80, int(w * o["width"] / dpr)))
        self.adjustSize()
        cx, cy = l + o["pos_x"] * w, t + o["pos_y"] * h
        self.move(int(cx / dpr - self.width() / 2), int(cy / dpr - self.height() / 2))
        return True

    def refresh(self):
        self.apply_style()
        if self.isVisible():
            self.place(allow_fallback=self.edit or self.sample)

    # --- العرض ---
    def _show(self, text, secs):
        if not CFG["overlay"]["enabled"]:
            self.hide()
            return
        if self.edit or self.sample:
            return
        text, _, orig = text.partition("\x1e")  # النص الأصلي (إذا الخيار مفعّل) يجي بعد فاصل خاص
        if not text:
            self.hide()
            return
        if orig and CFG["audio"].get("display_mode") == "both":
            size = CFG["overlay"]["font_size"] * self.font_scale() * 0.7
            self.label.setTextFormat(QtCore.Qt.RichText)
            self.label.setText(f"<div dir='ltr' style='font-size:{size:.1f}pt;font-weight:normal;color:#c8c8c8'>"
                               + html.escape(orig) + "</div><div>" + html.escape(text).replace("\n", "<br>") + "</div>")
        else:
            self.label.setTextFormat(QtCore.Qt.PlainText)
            self.label.setText(text)
        if self.place():
            self.show()
            if secs:
                self.timer.start(int(secs * 1000))

    def _expire(self):
        if not (self.edit or self.sample):
            self.hide()

    def _preview(self):
        if self.edit or self.sample:
            self.label.setTextFormat(QtCore.Qt.PlainText)
            self.label.setText(SAMPLE_EDIT if self.edit else SAMPLE)
            self.apply_style()
            self.place(allow_fallback=True)
            self.show()
        else:
            self.hide()

    def set_edit(self, on):
        self.edit = on
        set_click_through(self, not on)
        self.setMouseTracking(on)
        if not hasattr(self, "grip"):
            self.grip = Grip(self)
        self.grip.setGeometry(self.rect())
        self.grip.setVisible(on)
        self.grip.raise_()
        self._preview()
        self.grip.setGeometry(self.rect())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "grip"):
            self.grip.setGeometry(self.rect())
            self.grip.raise_()

    def _hit(self, pos):
        """'font' للزاوية، 'width' للحافة اليمين/اليسار، 'pad' للحافة فوق/تحت، وإلا None."""
        x, y, w, h = pos.x(), pos.y(), self.width(), self.height()
        cz = max(12, min(CORNER, h * 0.34))      # الزاوية تصغر مع قصر المربع عشان تبقى الحافة قابلة للمسك
        ez = max(8, min(EDGE, h * 0.25))
        if (x < cz or x > w - cz) and (y < cz or y > h - cz):
            return "font"
        if x < EDGE or x > w - EDGE:
            return "width"
        if y < ez or y > h - ez:
            return "pad"
        return None

    def set_sample(self, on):
        self.sample = on
        self._preview()

    # --- السحب بالماوس ---
    def mousePressEvent(self, e):
        if self.edit and e.button() == QtCore.Qt.LeftButton:
            mode = self._hit(e.position())
            if mode:
                c = self.frameGeometry().center()
                g = e.globalPosition()
                o = CFG["overlay"]
                dist = max(10.0, ((g.x() - c.x()) ** 2 + (g.y() - c.y()) ** 2) ** 0.5)
                dx, dy = max(10.0, abs(g.x() - c.x())), max(10.0, abs(g.y() - c.y()))
                self._rs = dict(mode=mode, c=c, dist=dist, dx=dx, dy=dy, font=o["font_size"], width=o["width"],
                                pad=o["pad_y"], h=max(30, self.height()))
            else:
                self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._rs is not None:
            r, g, o = self._rs, e.globalPosition(), CFG["overlay"]
            c = r["c"]
            if r["mode"] == "font":  # زاوية: تكبير/تصغير الخط (مربوط بارتفاع المربع)
                d = ((g.x() - c.x()) ** 2 + (g.y() - c.y()) ** 2) ** 0.5
                o["font_size"] = int(clamp(r["font"] * max(0.2, 1 + (d - r["dist"]) / (r["h"] * 2.0)), 14, 200))
            elif r["mode"] == "width":  # حافة يمين/يسار: مطّ وتقصير العرض
                k = abs(g.x() - c.x()) / r["dx"]
                o["width"] = round(clamp(r["width"] * k, 0.15, 1.0), 3)
                o["font_size"] = int(clamp(r["font"] * k, 14, 200))  # الحروف تتكبر وتتصغر مع المطّ
            else:  # حافة فوق/تحت: ارتفاع المربع
                o["pad_y"] = int(clamp(r["pad"] + (abs(g.y() - c.y()) - r["dy"]), 2, 200))
            self.refresh()
        elif self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)
        elif self.edit:
            m = self._hit(e.position())
            self.setCursor({"font": QtCore.Qt.SizeFDiagCursor, "width": QtCore.Qt.SizeHorCursor,
                            "pad": QtCore.Qt.SizeVerCursor}.get(m, QtCore.Qt.SizeAllCursor))

    def mouseReleaseEvent(self, e):
        if self._rs is not None:
            self._rs = None
            self.placed.emit()
        elif self._drag is not None:
            self._drag = None
            (l, t, r, b), _ = area_rect(self)
            dpr = self.devicePixelRatioF()
            c = self.frameGeometry().center()
            CFG["overlay"]["pos_x"] = round(clamp((c.x() * dpr - l) / (r - l), 0, 1), 4)
            CFG["overlay"]["pos_y"] = round(clamp((c.y() * dpr - t) / (b - t), 0, 1), 4)
            self.placed.emit()

    def wheelEvent(self, e):
        """العجلة = تكبير/تصغير الخط. مع Shift = عرض المربع."""
        if self.edit:
            o = CFG["overlay"]
            step = e.angleDelta().y() / 120
            if e.modifiers() & QtCore.Qt.ShiftModifier:
                o["width"] = round(clamp(o["width"] + step * 0.02, 0.15, 1.0), 3)
            else:
                o["font_size"] = int(clamp(o["font_size"] + step * 3, 14, 200))
            self.refresh()
            self.placed.emit()


class RegionEditor(QtWidgets.QWidget):
    """مستطيل شفاف تسحبه وتغيّر حجمه ليحدد منطقة قراءة النص من الشاشة."""
    changed = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setMinimumSize(120, 50)
        self.grip = QtWidgets.QSizeGrip(self)
        self._drag = None
        self._loading = False
        self.timer = QtCore.QTimer(singleShot=True, interval=250)
        self.timer.timeout.connect(self._commit)

    def open(self):
        (l, t, r, b), _ = area_rect(self)
        x0, y0, x1, y1 = CFG["screen"]["region"]
        w, h, dpr = r - l, b - t, self.devicePixelRatioF()
        self._loading = True
        self.setGeometry(int((l + x0 * w) / dpr), int((t + y0 * h) / dpr),
                         int((x1 - x0) * w / dpr), int((y1 - y0) * h / dpr))
        self._loading = False
        self.show()
        exclude_from_capture(self)

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(0, 200, 255, 45))
        p.setPen(QtGui.QPen(QtGui.QColor(0, 200, 255), 3))
        p.drawRect(self.rect().adjusted(1, 1, -2, -2))
        p.setFont(QtGui.QFont("Segoe UI", 13, QtGui.QFont.Bold))
        msg = "منطقة قراءة النص\nاسحبها لتحريكها • اسحب الزاوية لتغيير الحجم"
        tr = p.fontMetrics().boundingRect(self.rect(), QtCore.Qt.AlignCenter, msg).adjusted(-14, -8, 14, 8)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(0, 0, 0, 190))  # خلفية داكنة عشان الكتابة تنقرا فوق أي لقطة
        p.drawRoundedRect(tr, 8, 8)
        p.setPen(QtGui.QColor(255, 255, 255))
        p.drawText(self.rect(), QtCore.Qt.AlignCenter, msg)

    def resizeEvent(self, _):
        self.grip.move(self.width() - self.grip.width(), self.height() - self.grip.height())
        self._schedule()

    def moveEvent(self, _):
        self._schedule()

    def _schedule(self):
        if not self._loading:
            self.timer.start()

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _):
        self._drag = None

    def _commit(self):
        (l, t, r, b), _ = area_rect(self)
        dpr, g = self.devicePixelRatioF(), self.geometry()
        w, h = r - l, b - t
        x0 = clamp((g.left() * dpr - l) / w, 0, 0.98)
        y0 = clamp((g.top() * dpr - t) / h, 0, 0.98)
        x1 = clamp(((g.right() + 1) * dpr - l) / w, x0 + 0.02, 1)
        y1 = clamp(((g.bottom() + 1) * dpr - t) / h, y0 + 0.02, 1)
        CFG["screen"]["region"] = [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]
        self.changed.emit()


LANGS = [("تلقائي", "auto"), ("English", "en"), ("日本語", "ja"), ("한국어", "ko"), ("中文", "zh"),
         ("Français", "fr"), ("Deutsch", "de"), ("Español", "es"), ("Русский", "ru"), ("Türkçe", "tr")]


class Panel(QtWidgets.QWidget):
    quit_req = QtCore.Signal()
    toggle_req = QtCore.Signal()
    front_req = QtCore.Signal()
    upd_msg = QtCore.Signal(str)
    upd_found = QtCore.Signal(object)
    upd_prog = QtCore.Signal(float)
    prep_msg = QtCore.Signal(str)
    mode_req = QtCore.Signal()

    def bring_to_front(self):
        """يطلّع اللوحة فوق اللعبة (Asobi بملء الشاشة يغطيها) بدون ما تبقى دايماً فوقها."""
        self.showNormal()
        h = wt.HWND(int(self.winId()))
        for z in (-1, -2):  # TOPMOST ثم NOTOPMOST: ترتفع فوق النوافذ وتتعامل بعدها كنافذة عادية
            u32.SetWindowPos(h, wt.HWND(z), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
        u32.SetForegroundWindow(h)

    def __init__(self, start_engine=True):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setObjectName("root")
        self.setLayoutDirection(QtCore.Qt.RightToLeft)
        if ICON.exists():
            self.setWindowIcon(QtGui.QIcon(str(ICON)))
        scr = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        self.setMinimumWidth(820)
        self.resize(940, min(780, scr.height() - 80))
        self.upd = None  # manifest التحديث المتوفر
        # البث والتسجيل: يشتغل تلقائياً بدون خيارات (الترجمة تظهر للمشاهدين، والنص الأصلي مخفي)
        CFG["overlay"].update(visible_in_capture=True, obs_window=False, show_original=False)
        CFG["audio"].setdefault("display_mode", "translate")
        CFG["audio"].update(language="auto", live=True)
        CFG["screen"]["enabled"] = False  # قراءة الشاشة محذوفة من البرنامج
        CFG["overlay"]["font"] = "Segoe UI"  # خط واحد ثابت للترجمة
        self.move(scr.center() - self.rect().center())  # دايماً بنص الشاشة الرئيسية، مو مقطوعة على الحافة
        self.overlay, self.region = Overlay(), RegionEditor()
        self.audio = None
        self.save_timer = QtCore.QTimer(singleShot=True, interval=400)
        self.save_timer.timeout.connect(T.save_config)
        T.RUN["on"] = bool(CFG["auto_start"])
        self._build()
        self.sync()
        self._update_run_btn()
        self.overlay.placed.connect(self._after_drag)
        self.region.changed.connect(self._dirty)
        self._build_tray()
        self.quit_req.connect(self.close)
        self.mode_req.connect(self._cycle_mode)
        self.front_req.connect(self.bring_to_front)
        QtCore.QTimer.singleShot(400, self.bring_to_front)
        self.toggle_req.connect(lambda: self.cb_show.setChecked(not self.cb_show.isChecked()))
        self.poll = QtCore.QTimer(interval=500)
        self.poll.timeout.connect(self._poll)
        self.poll.start()
        if start_engine:
            threading.Thread(target=self._boot, daemon=True).start()

    # ---------- بناء الواجهة ----------
    def _group(self, title):
        box = QtWidgets.QGroupBox(title)
        form = QtWidgets.QFormLayout(box)
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        self.col.addWidget(box)
        return form

    def _slider(self, lo, hi, cb, suffix=""):
        s = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        s.setRange(lo, hi)
        lbl = QtWidgets.QLabel("")
        lbl.setMinimumWidth(48)
        s.valueChanged.connect(lambda v: (lbl.setText(f"{v}{suffix}"), cb(v)))
        row = QtWidgets.QHBoxLayout()
        row.addWidget(s, 1)
        row.addWidget(lbl)
        w = QtWidgets.QWidget()
        w.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        w.slider, w.label = s, lbl
        return w

    def _color_btn(self, key):
        b = QtWidgets.QPushButton("اختيار")
        b.clicked.connect(lambda: self._pick_color(key, b))
        return b

    def _build(self):
        o, sc, au = CFG["overlay"], CFG["screen"], CFG["audio"]
        self.adv = []  # عناصر تظهر فقط في وضع الإعدادات المتقدمة
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ----- القائمة الجانبية -----
        side = QtWidgets.QFrame()
        side.setObjectName("side")
        side.setFixedWidth(210)
        sl = QtWidgets.QVBoxLayout(side)
        sl.setContentsMargins(0, 22, 0, 14)
        sl.setSpacing(2)
        logo = QtWidgets.QLabel()
        if ICON.exists():
            logo.setPixmap(QtGui.QPixmap(str(ICON)).scaled(72, 72, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        logo.setAlignment(QtCore.Qt.AlignCenter)
        t1 = QtWidgets.QLabel(APP_NAME)
        t1.setObjectName("title")
        t1.setAlignment(QtCore.Qt.AlignCenter)
        t2 = QtWidgets.QLabel(f"الإصدار {VERSION}")
        t2.setObjectName("ver")
        t2.setAlignment(QtCore.Qt.AlignCenter)
        sl.addWidget(logo)
        sl.addWidget(t1)
        sl.addWidget(t2)
        sl.addSpacing(18)
        self.stack = QtWidgets.QStackedWidget()
        self.navs = []

        def page(name, icon, hidden=False):
            sc_ = QtWidgets.QScrollArea(widgetResizable=True)
            sc_.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            inner = QtWidgets.QWidget()
            sc_.setWidget(inner)
            col = QtWidgets.QVBoxLayout(inner)
            col.setContentsMargins(24, 22, 24, 22)
            col.setSpacing(14)
            i = self.stack.addWidget(sc_)
            b = QtWidgets.QPushButton(f"{icon}   {name}")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.clicked.connect(lambda _=False, i=i: self.stack.setCurrentIndex(i))
            if hidden:
                b.hide()
            sl.addWidget(b)
            self.navs.append(b)
            self.col = col

        def title(text, sub=""):
            l = QtWidgets.QLabel(text)
            l.setObjectName("h1")
            self.col.addWidget(l)
            if sub:
                m = QtWidgets.QLabel(sub)
                m.setObjectName("muted")
                m.setWordWrap(True)
                self.col.addWidget(m)

        def row(f, label, w, adv=False):
            lab = QtWidgets.QLabel(label + ":") if label else None
            if lab:
                f.addRow(lab, w)
            else:
                f.addRow(w)
            if adv:
                self.adv += [x for x in (lab, w) if x]

        # ===== 1) الرئيسية =====
        page("الرئيسية", "◉")
        title("لوحة التحكم", "اتصل بالبلايستيشن من Asobi وبعدين اضغط ابدأ.")
        self.btn_run = QtWidgets.QPushButton()
        self.btn_run.setObjectName("primary")
        self.btn_run.setMinimumHeight(64)
        self.btn_run.clicked.connect(self._toggle_run)
        self.col.addWidget(self.btn_run)
        self.cb_auto = Toggle("ابدأ الترجمة تلقائياً عند فتح البرنامج")
        self.cb_auto.toggled.connect(lambda v: self._set(CFG, "auto_start", v))
        self.col.addWidget(self.cb_auto)
        self.lb_asobi, self.lb_tr = QtWidgets.QLabel(), QtWidgets.QLabel()
        self.lb_ocr, self.lb_aud, self.lb_heard = QtWidgets.QLabel(), QtWidgets.QLabel(), QtWidgets.QLabel()
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        for k, (n, w) in enumerate((("Asobi", self.lb_asobi), ("الترجمة", self.lb_tr),
                                    ("سماع الصوت", self.lb_aud))):
            tile = QtWidgets.QFrame()
            tile.setObjectName("tile")
            tl = QtWidgets.QVBoxLayout(tile)
            a = QtWidgets.QLabel(n)
            a.setObjectName("tt")
            w.setObjectName("tv")
            w.setWordWrap(True)
            tl.addWidget(a)
            tl.addWidget(w)
            grid.addWidget(tile, k // 2, k % 2, 1, 2 if k == 2 else 1)
        self.col.addLayout(grid)
        tile = QtWidgets.QFrame()
        tile.setObjectName("tile")
        tl = QtWidgets.QVBoxLayout(tile)
        a = QtWidgets.QLabel("آخر جملة سمعها")
        a.setObjectName("tt")
        self.lb_heard.setObjectName("tv")
        self.lb_heard.setWordWrap(True)
        tl.addWidget(a)
        tl.addWidget(self.lb_heard)
        self.col.addWidget(tile)
        f = self._group("ماذا تترجم؟")
        self.cb_show = Toggle("إظهار الترجمة على الشاشة  (Ctrl+Alt+H)")
        self.cb_audio = Toggle("ترجمة صوت اللعبة")
        self.cb_screen = Toggle("ترجمة نص الشاشة")
        self.cb_show.toggled.connect(lambda v: self._set(o, "enabled", v))
        self.cb_screen.toggled.connect(lambda v: self._set(sc, "enabled", v))
        self.cb_audio.toggled.connect(lambda v: self._set(au, "enabled", v))
        for w in (self.cb_show, self.cb_audio):
            f.addRow(w)
        self.col.addStretch(1)

        # ===== 2) المظهر والمكان =====
        page("المظهر والمكان", "◧")
        title("شكل الترجمة ومكانها", "تحكم بشكل الترجمة ومكانها، وبالمنطقة اللي يقرا منها نص الشاشة.")
        f = self._group("المظهر")
        self.fontbox = QtWidgets.QFontComboBox()
        self.fontbox.currentFontChanged.connect(lambda fnt: self._set(o, "font", fnt.family()))
        self.sl_size = self._slider(14, 200, lambda v: self._set(o, "font_size", v), " px")
        self.sl_tcol = self._color_btn("text_color")
        self.sl_top = self._slider(10, 100, lambda v: self._set(o, "text_opacity", v), "%")
        self.sl_bcol = self._color_btn("bg_color")
        self.sl_bop = self._slider(0, 100, lambda v: self._set(o, "bg_opacity", v), "%")
        self.sl_rad = self._slider(0, 40, lambda v: self._set(o, "radius", v), " px")
        self.sl_pad = self._slider(2, 200, lambda v: self._set(o, "pad_y", v), " px")
        row(f, "حجم الخط", self.sl_size)
        row(f, "لون الكتابة", self.sl_tcol)
        row(f, "لون الخلفية", self.sl_bcol)
        row(f, "شفافية الخلفية", self.sl_bop)
        self.btn_sample = QtWidgets.QPushButton("عرض نص تجريبي")
        self.btn_sample.setCheckable(True)
        self.btn_sample.toggled.connect(self.overlay.set_sample)
        f.addRow(self.btn_sample)
        f = self._group("المكان")
        self.btn_edit = QtWidgets.QPushButton("عدّل الترجمة بالماوس  (تحريك • تكبير • مطّ • تقصير)")
        self.btn_edit.setCheckable(True)
        self.btn_edit.toggled.connect(self.overlay.set_edit)
        f.addRow(self.btn_edit)
        prow = QtWidgets.QHBoxLayout()
        for name, y in (("أعلى", 0.1), ("وسط", 0.5), ("أسفل", 0.9)):
            b = QtWidgets.QPushButton(name)
            b.clicked.connect(lambda _=False, y=y: self._preset(y))
            prow.addWidget(b)
        pw = QtWidgets.QWidget()
        pw.setLayout(prow)
        prow.setContentsMargins(0, 0, 0, 0)
        row(f, "أماكن جاهزة", pw)
        self.sp = {}
        for key, name in (("pos_x", "الموضع الأفقي %"), ("pos_y", "الموضع العمودي %"), ("width", "عرض الترجمة %")):
            s_ = QtWidgets.QDoubleSpinBox()
            s_.setLocale(QtCore.QLocale(QtCore.QLocale.English))  # أرقام عادية 0-9
            s_.setRange(0, 100)
            s_.setDecimals(1)
            s_.setSingleStep(0.5)
            s_.valueChanged.connect(lambda v, k=key: self._pos_changed(k, v))
            self.sp[key] = s_
            # بدون صف في الواجهة: المكان والعرض يتحكم فيهم بالماوس فقط (الأداة تبقى للمزامنة الداخلية)
        btn = QtWidgets.QPushButton("استرجاع المظهر والمكان الافتراضي")
        btn.clicked.connect(self._reset_overlay)
        f.addRow(btn)
        self.adv.append(btn)
        self.btn_region = QtWidgets.QPushButton("حدّد منطقة قراءة النص بالماوس")
        self.btn_region.setCheckable(True)
        self.btn_region.toggled.connect(lambda on: self.region.open() if on else self.region.hide())
        self.sl_conf = self._slider(20, 95, lambda v: self._set(sc, "min_confidence", v / 100), "%")
        self.sl_letters = self._slider(2, 15, lambda v: self._set(sc, "min_letters", v), " حرف")
        self.col.addStretch(1)

        # ===== 3) الصوت =====
        page("صوت اللعبة", "♪", hidden=True)  # اللغة تتحدد تلقائياً (إنجليزي/ياباني/كوري/صيني...)
        title("سماع الحوار", "يلتقط صوت Asobi فقط، ما يسمع Discord ولا باقي الجهاز.")
        f = self._group("الأساسي")
        self.lang = QtWidgets.QComboBox()
        for n, c in LANGS:
            self.lang.addItem(n, c)
        self.lang.currentIndexChanged.connect(lambda: self._set(au, "language", self.lang.currentData()))
        self.cb_live = Toggle("ترجمة فورية أثناء الكلام (بدون انتظار نهاية الجملة)")
        self.cb_live.toggled.connect(lambda v: self._set(au, "live", v))
        self.ed_hint = QtWidgets.QLineEdit()
        self.ed_hint.setPlaceholderText("أسماء الشخصيات والأماكن بالإنجليزي، تفصل بينها فاصلة")
        self.ed_hint.editingFinished.connect(lambda: self._set(au, "hint_words", self.ed_hint.text()))
        f.addRow(self.cb_live)
        row(f, "لغة الكلام", self.lang)
        row(f, "كلمات اللعبة", self.ed_hint)
        f = self._group("متقدم")
        self.dev = QtWidgets.QComboBox()
        self.dev.addItem("تلقائي (الافتراضي)", "auto")
        try:
            for n in T.list_loopbacks():
                self.dev.addItem(n, n)
        except Exception as e:
            print("[صوت] تعذر سرد الأجهزة:", e, flush=True)
        self.dev.currentIndexChanged.connect(self._device_changed)
        self.src = QtWidgets.QComboBox()
        self.src.addItem("صوت Asobi فقط (مُوصى به)", "app")
        self.src.addItem("كل أصوات الجهاز", "system")
        self.src.currentIndexChanged.connect(self._source_changed)
        self.cb_ar = Toggle("عرض الكلام العربي بدون ترجمة")
        self.cb_ar.toggled.connect(lambda v: self._set(au, "show_arabic", v))
        self.cb_boost = Toggle("تقوية الصوت الهادي")
        self.cb_boost.toggled.connect(lambda v: self._set(au, "boost_quiet", v))
        self.sl_vad = self._slider(20, 90, lambda v: self._set(au, "vad_threshold", v / 100), "%")
        self.sl_hide = self._slider(2, 15, lambda v: self._set(au, "hide_after_seconds", v), " ث")
        self.sp_live = QtWidgets.QDoubleSpinBox()
        self.sp_live.setLocale(QtCore.QLocale(QtCore.QLocale.English))
        self.sp_live.setRange(0.3, 3.0)
        self.sp_live.setSingleStep(0.1)
        self.sp_live.setSuffix(" ث")
        self.sp_live.valueChanged.connect(lambda v: self._set(au, "live_interval", round(v, 2)))
        self.cb_tent = Toggle("عرض الكلمات غير المؤكدة مؤقتاً (أسرع، وتتصحح بعد نهاية الجملة)")
        self.cb_tent.toggled.connect(lambda v: self._set(au, "live_tentative", v))
        self.cb_acc = Toggle("دقة عالية في السماع (أبطأ شوي)")
        self.cb_acc.toggled.connect(lambda v: self._set(au, "high_accuracy", v))
        row(f, "مصدر الصوت", self.src, True)
        row(f, "جهاز الصوت", self.dev, True)
        row(f, "مدة بقاء الترجمة", self.sl_hide, True)
        row(f, "سرعة التحديث", self.sp_live, True)
        row(f, "حساسية الكلام", self.sl_vad, True)
        for w in (self.cb_tent, self.cb_acc, self.cb_boost, self.cb_ar):
            row(f, "", w, True)
        self.adv_audio_group = f
        self.col.addStretch(1)

        # ===== 5) البث =====
        page("البث والتسجيل", "●", hidden=True)  # بدون خيارات للمستخدم: الترجمة تظهر في البث دائماً
        title("الظهور للناس", "عشان المشاهدين يشوفون الترجمة في Discord وOBS.")
        f = self._group("الخيارات")
        self.cb_vis = Toggle("تظهر الترجمة في البث والتسجيل")
        self.cb_vis.toggled.connect(lambda v: (self._set(o, "visible_in_capture", v), self.overlay.apply_capture()))
        self.cb_orig = Toggle("إظهار النص الأصلي تحت الترجمة (للتأكد من الدقة)")
        self.cb_orig.toggled.connect(lambda v: self._set(o, "show_original", v))
        self.cb_obs = Toggle("وضع OBS: الترجمة نافذة مستقلة تقدر تضيفها كمصدر")
        self.cb_obs.toggled.connect(lambda v: (self._set(o, "obs_window", v), self.overlay.apply_capture()))
        f.addRow(self.cb_vis)
        f.addRow(self.cb_orig)
        row(f, "", self.cb_obs, True)
        tip = QtWidgets.QLabel("في Discord اختر «مشاركة الشاشة» (مو نافذة اللعبة) عشان الترجمة تظهر للناس. "
                               "في OBS استخدم «التقاط الشاشة»، أو «التقاط نافذة» للعبة + نافذة "
                               "Asobi Translation Overlay مع تفعيل وضع OBS.")
        tip.setWordWrap(True)
        tip.setObjectName("muted")
        self.col.addWidget(tip)
        self.col.addStretch(1)

        # ===== 6) التحديثات =====
        page("الإعدادات", "⚙")
        title("الإعدادات")
        f = self._group("عام")
        self.cb_adv = Toggle("إظهار الإعدادات المتقدمة (خيارات إضافية في الصفحات)")
        self.cb_adv.toggled.connect(self._adv_changed)
        f.addRow(self.cb_adv)
        f = self._group("الأداء")
        self.lb_prof = QtWidgets.QLabel("—")
        self.lb_prof.setWordWrap(True)
        f.addRow(self.lb_prof)
        self.cmb_prof = QtWidgets.QComboBox()
        self.cmb_prof.addItem("تلقائي (حسب كرت الشاشة)", "auto")
        for n in profiles.ORDER:
            self.cmb_prof.addItem(profiles.PROFILES[n]["label"], n)
        self.cmb_prof.currentIndexChanged.connect(self._prof_changed)
        row(f, "ملف الأداء", self.cmb_prof)
        self.btn_prep = QtWidgets.QPushButton("نزّل نماذج الملف المختار")
        self.btn_prep.clicked.connect(self._prepare_models)
        row(f, "", self.btn_prep)
        self.lb_prep = QtWidgets.QLabel("تغيير ملف الأداء يحتاج إعادة تشغيل البرنامج. الأعلى أدق، والأخف أسرع ويناسب كروت أضعف.")
        self.lb_prep.setObjectName("muted")
        self.lb_prep.setWordWrap(True)
        row(f, "", self.lb_prep)
        self.prep_msg.connect(lambda m: (self.lb_prep.setText(m), self.btn_prep.setEnabled(True)))
        f = self._group("عرض الكلام")
        self.cmb_mode = QtWidgets.QComboBox()
        for label, key in MODES:
            self.cmb_mode.addItem(label, key)
        self.cmb_mode.currentIndexChanged.connect(lambda: self._set(au, "display_mode", self.cmb_mode.currentData()))
        row(f, "اللي يظهر على الشاشة", self.cmb_mode)
        self.cb_hist = Toggle("حفظ سجل الحوار في ملف")
        self.cb_hist.toggled.connect(lambda v: self._set(au, "save_history", v))
        f.addRow(self.cb_hist)
        btn_log = QtWidgets.QPushButton("فتح سجل الحوار")
        btn_log.clicked.connect(self._open_log)
        f.addRow(btn_log)
        tipm = QtWidgets.QLabel("الاختصار Ctrl+Alt+M يبدّل بين الأوضاع وأنت تلعب.")
        tipm.setObjectName("muted")
        f.addRow(tipm)
        self.adv += [f.parentWidget()]
        f = self._group("عن البرنامج")
        ab = QtWidgets.QLabel(f"<b>{APP_NAME}</b> — الإصدار {VERSION}<br>يترجم صوت ألعاب الريموت بلاي إلى العربية فوراً، "
                              "ويقدر يكتب الكلام الأصلي كلمة كلمة. ما يعدّل Asobi ولا يتجاوز أي حماية.")
        ab.setWordWrap(True)
        f.addRow(ab)
        btn_site = QtWidgets.QPushButton("صفحة البرنامج على GitHub")
        btn_site.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(REPO_URL)))
        f.addRow(btn_site)
        lic = QtWidgets.QLabel("نموذج الترجمة NLLB-200 من Meta بترخيص غير تجاري (CC-BY-NC 4.0)، فالبرنامج مجاني ولا يُباع.")
        lic.setObjectName("muted")
        lic.setWordWrap(True)
        f.addRow(lic)
        f = self._group("التحديثات")
        self.lb_upd = QtWidgets.QLabel(f"الإصدار الحالي {VERSION}")
        self.lb_upd.setWordWrap(True)
        self.pb_upd = QtWidgets.QProgressBar()
        self.pb_upd.setRange(0, 1000)
        self.pb_upd.hide()
        self.btn_chk = QtWidgets.QPushButton("تحقق من التحديثات")
        self.btn_chk.clicked.connect(lambda: self._check_update(True))
        self.btn_inst = QtWidgets.QPushButton("نزّل وركّب التحديث")
        self.btn_inst.setObjectName("primary")
        self.btn_inst.hide()
        self.btn_inst.clicked.connect(self._install_update)
        self.cb_updauto = Toggle("تحديث البرنامج تلقائياً (بدون سؤال)")
        self.cb_updauto.toggled.connect(lambda v: self._set(CFG["update"], "auto_check", v))
        for w in (self.lb_upd, self.pb_upd, self.btn_chk, self.btn_inst, self.cb_updauto):
            f.addRow(w)
        self.upd_msg.connect(self._upd_msg)
        self.upd_found.connect(self._upd_found)
        self.upd_prog.connect(lambda x: (self.pb_upd.show(), self.pb_upd.setValue(int(x * 1000))))
        self.pending = None  # (مجلد الملفات, الإصدار) تحديث منزّل ينتظر وقت مناسب للتركيب
        QtCore.QTimer.singleShot(8000, self._auto_update)
        self.auto_timer = QtCore.QTimer(interval=6 * 3600 * 1000)  # نعيد التحقق كل 6 ساعات
        self.auto_timer.timeout.connect(self._auto_update)
        self.auto_timer.start()
        self.col.addStretch(1)

        # ----- أسفل القائمة -----
        sl.addStretch(1)
        root.addWidget(side)
        root.addWidget(self.stack, 1)
        self.navs[0].setChecked(True)

    def _adv_changed(self, v):
        CFG["ui"]["advanced"] = bool(v)
        self._apply_adv()
        self._dirty()

    def _apply_adv(self):
        on = bool(CFG["ui"]["advanced"])
        for w in self.adv:
            w.setVisible(on)
        self.adv_audio_group.parentWidget().setVisible(on)  # مجموعة «متقدم» كاملة

    # ---------- منطق الإعدادات ----------
    def _dirty(self):
        self.save_timer.start()

    def _set(self, d, key, v):
        d[key] = v
        self.overlay.refresh()
        self._dirty()

    def _pick_color(self, key, btn):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(CFG["overlay"][key]), self, "اختر اللون")
        if c.isValid():
            CFG["overlay"][key] = c.name()
            self._swatch(btn, c.name())
            self.overlay.refresh()
            self._dirty()

    @staticmethod
    def _swatch(btn, color):
        fg = "#000" if QtGui.QColor(color).lightness() > 128 else "#fff"
        btn.setStyleSheet(f"background:{color};color:{fg};")

    def _pos_changed(self, key, v):
        CFG["overlay"][key] = round(v / 100, 4)
        self.overlay.refresh()
        self._dirty()

    def _preset(self, y):
        CFG["overlay"]["pos_x"], CFG["overlay"]["pos_y"] = 0.5, y
        self.sync()
        self.overlay.refresh()
        self._dirty()

    def _after_drag(self):
        self.sync()
        self._dirty()

    def _reset_overlay(self):
        CFG["overlay"].update(copy.deepcopy(T.DEFAULTS["overlay"]))
        self.sync()
        self.overlay.refresh()
        self._dirty()

    def _build_tray(self):
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QtWidgets.QSystemTrayIcon(QtGui.QIcon(str(ICON)), self)
        menu = QtWidgets.QMenu()
        menu.addAction("فتح اللوحة", self.bring_to_front)
        menu.addAction("ابدأ / أوقف الترجمة", self._toggle_run)
        menu.addAction("تبديل وضع العرض", self._cycle_mode)
        menu.addSeparator()
        menu.addAction("خروج", self.close)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(lambda r: self.bring_to_front() if r in (
            QtWidgets.QSystemTrayIcon.Trigger, QtWidgets.QSystemTrayIcon.DoubleClick) else None)
        self.tray.show()

    # ---------- أوضاع العرض ----------
    def _cycle_mode(self):
        keys = [k for _, k in MODES]
        cur = CFG["audio"].get("display_mode", "translate")
        CFG["audio"]["display_mode"] = keys[(keys.index(cur) + 1) % len(keys)] if cur in keys else keys[0]
        self.cmb_mode.blockSignals(True)
        self.cmb_mode.setCurrentIndex(max(0, self.cmb_mode.findData(CFG["audio"]["display_mode"])))
        self.cmb_mode.blockSignals(False)
        names = dict((k, l) for l, k in MODES)
        self.overlay.show_text.emit(names[CFG["audio"]["display_mode"]], 1.5)
        self._dirty()

    def _open_log(self):
        f = T.BASE / "transcript.log"
        try:
            f.touch(exist_ok=True)
            os.startfile(str(f))
        except OSError:
            pass

    # ---------- ملف الأداء ----------
    def _prof_changed(self):
        CFG["performance"]["profile"] = self.cmb_prof.currentData()
        self._dirty()
        self.lb_prep.setText("أعد تشغيل البرنامج عشان يشتغل الملف الجديد. إذا نماذجه غير مثبتة اضغط «نزّل نماذج الملف المختار».")

    def _prepare_models(self):
        import subprocess
        want = CFG["performance"].get("profile", "auto")
        self.btn_prep.setEnabled(False)
        self.lb_prep.setText("جاري التنزيل والتحويل... ممكن ياخذ وقت حسب الإنترنت.")

        def run():
            try:
                py = sys.executable.replace("pythonw.exe", "python.exe")
                r = subprocess.run([py, "-u", str(T.BASE / "prepare_models.py"), want], cwd=str(T.BASE),
                                   creationflags=0x08000000, capture_output=True, text=True, encoding="utf-8")
                self.prep_msg.emit("تم تجهيز النماذج ✓ أعد تشغيل البرنامج." if r.returncode == 0
                                   else "فشل التنزيل: " + (r.stderr or r.stdout)[-200:])
            except Exception as e:
                self.prep_msg.emit(f"فشل التنزيل: {e}")
        threading.Thread(target=run, daemon=True).start()

    # ---------- التحديث ----------
    def _upd_msg(self, s):
        self.lb_upd.setText(s)
        self.btn_chk.setEnabled(True)
        self.btn_inst.setEnabled(True)

    def _upd_found(self, m):
        self.upd = m
        notes = f"\n{m['notes']}" if m.get("notes") else ""
        self.lb_upd.setText(f"يتوفر إصدار جديد {m['version']} (أنت على {VERSION}){notes}")
        self.btn_inst.show()
        self.btn_chk.setEnabled(True)

    def _auto_update(self):
        """تحديث تلقائي بدون أي سؤال: يتحقق، ينزّل، يتحقق من البصمة، ثم يركّب لما الترجمة تكون واقفة."""
        if not CFG["update"]["auto_check"] or self.pending or not hasattr(self, "lb_upd"):
            return

        def run():
            try:
                m, msg = updater.check()
                if not m:
                    return
                self.upd_msg.emit(f"جاري تنزيل التحديث {m['version']} تلقائياً...")
                d = updater.download(m)
                updater.write_ready(m["version"])
                self.pending = (d, m["version"])
                self.upd_msg.emit(f"التحديث {m['version']} جاهز، يتركب تلقائياً لما توقف الترجمة.")
            except Exception as e:
                print("[تحديث] فشل التحديث التلقائي:", e, flush=True)
        threading.Thread(target=run, daemon=True).start()

    def _check_update(self, manual):
        self.btn_chk.setEnabled(False)
        self.lb_upd.setText("جاري التحقق...")

        def run():
            m, msg = updater.check()
            if m:
                self.upd_found.emit(m)
            else:
                self.upd_msg.emit(msg if manual or "جديد" in msg else f"الإصدار الحالي {VERSION}")
        threading.Thread(target=run, daemon=True).start()

    def _install_update(self):
        if not self.upd:
            return
        m = self.upd
        self.btn_inst.setEnabled(False)
        self.btn_chk.setEnabled(False)
        self.lb_upd.setText("جاري تنزيل التحديث...")

        def run():
            try:
                d = updater.download(m, self.upd_prog.emit)
            except Exception as e:
                self.upd_msg.emit(f"فشل التحديث: {e}")
                return
            self.upd_msg.emit("تم التنزيل، البرنامج بيعيد التشغيل...")
            T.save_config()
            updater.apply_and_exit(d, m["version"])
        threading.Thread(target=run, daemon=True).start()

    def _toggle_run(self):
        T.RUN["on"] = not T.RUN["on"]
        if not T.RUN["on"]:
            self.overlay.show_text.emit("", 0.0)
        self._update_run_btn()

    def _update_run_btn(self):
        on = T.RUN["on"]
        self.btn_run.setText("■  أوقف الترجمة" if on else "▶  ابدأ الترجمة")
        self.btn_run.setStyleSheet(
            "font-size:18px;font-weight:700;color:white;border-radius:6px;"
            + ("background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #e5484d,stop:1 #f2994a);" if on else ""))

    def _restart_audio(self):
        self._dirty()
        if self.audio:
            threading.Thread(target=self.audio.restart, daemon=True).start()

    def _device_changed(self):
        CFG["audio"]["device"] = self.dev.currentData()
        self._restart_audio()

    def _source_changed(self):
        CFG["audio"]["source"] = self.src.currentData()
        self.dev.setEnabled(CFG["audio"]["source"] == "system")
        self._restart_audio()

    def sync_pos(self):
        o = CFG["overlay"]
        for k, s in self.sp.items():
            s.blockSignals(True)
            s.setValue(o[k] * 100)
            s.blockSignals(False)

    def sync(self):
        """يحدّث كل عناصر اللوحة من الإعدادات (بدون ما يطلق تغييرات)."""
        o, sc, au = CFG["overlay"], CFG["screen"], CFG["audio"]
        for w in self.findChildren(QtWidgets.QWidget):
            w.blockSignals(True)
        self.cb_show.setChecked(o["enabled"])
        self.cb_screen.setChecked(sc["enabled"])
        self.cb_audio.setChecked(au["enabled"])
        self.fontbox.setCurrentFont(QtGui.QFont(o["font"]))
        for w, v in ((self.sl_size, o["font_size"]), (self.sl_top, o["text_opacity"]), (self.sl_bop, o["bg_opacity"]),
                     (self.sl_rad, o["radius"]), (self.sl_pad, o["pad_y"]), (self.sl_conf, int(sc["min_confidence"] * 100)),
                     (self.sl_letters, sc["min_letters"]), (self.sl_vad, int(au["vad_threshold"] * 100)),
                     (self.sl_hide, au["hide_after_seconds"])):
            w.slider.setValue(int(v))
        self._swatch(self.sl_tcol, o["text_color"])
        self._swatch(self.sl_bcol, o["bg_color"])
        self.dev.setCurrentIndex(max(0, self.dev.findData(au["device"])))
        self.lang.setCurrentIndex(max(0, self.lang.findData(au["language"])))
        self.cb_boost.setChecked(au["boost_quiet"])
        self.src.setCurrentIndex(max(0, self.src.findData(au["source"])))
        self.dev.setEnabled(au["source"] == "system")
        self.cb_ar.setChecked(au["show_arabic"])
        self.cb_acc.setChecked(au["high_accuracy"])
        self.cb_live.setChecked(au["live"])
        self.cb_tent.setChecked(au["live_tentative"])
        self.cb_vis.setChecked(o["visible_in_capture"])
        self.cb_obs.setChecked(o["obs_window"])
        self.cb_orig.setChecked(o["show_original"])
        self.sp_live.setValue(au["live_interval"])
        self.ed_hint.setText(au["hint_words"])
        self.cb_auto.setChecked(CFG["auto_start"])
        self.cb_updauto.setChecked(CFG["update"]["auto_check"])
        self.cmb_mode.setCurrentIndex(max(0, self.cmb_mode.findData(au.get("display_mode", "translate"))))
        self.cb_hist.setChecked(au.get("save_history", True))
        self.cb_adv.setChecked(CFG["ui"]["advanced"])
        self.cmb_prof.setCurrentIndex(max(0, self.cmb_prof.findData(CFG["performance"].get("profile", "auto"))))
        for w in self.findChildren(QtWidgets.QWidget):
            w.blockSignals(False)
        self.sync_pos()
        self._fix_labels()
        self._apply_adv()

    def _fix_labels(self):
        sfx = {self.sl_size: " px", self.sl_top: "%", self.sl_bop: "%", self.sl_rad: " px", self.sl_pad: " px", self.sl_conf: "%",
               self.sl_letters: " حرف", self.sl_vad: "%", self.sl_hide: " ث"}
        for w, s in sfx.items():
            w.label.setText(f"{w.slider.value()}{s}")

    # ---------- المحرك ----------
    def _emit(self, text, secs):
        if text:
            print("[عرض]", text, flush=True)
        self.overlay.show_text.emit(text, float(secs))

    def _boot(self):
        try:
            T.STATE["translation"] = "جاري التحميل..."
            mt = T.Translator()
            T.STATE["translation"] = "جاهز ✓"
        except Exception as e:
            T.STATE["translation"] = f"خطأ: {e}"
            return
        self.audio = T.AudioRunner(mt, self._emit)
        self.audio.start()

    def _vision(self, mt):
        try:
            T.vision_worker(mt, self._emit, threading.Event())
        except Exception as e:
            T.STATE["ocr"] = f"خطأ: {e}"
            print("[OCR] خطأ:", repr(e), flush=True)

    def _poll(self):
        win = T.find_window()
        self.lb_asobi.setText("مفتوح ✓" if win else "غير مفتوح — افتحه واتصل بالبلايستيشن")
        self.lb_tr.setText(T.STATE["translation"])
        self.lb_ocr.setText(T.STATE["ocr"])
        self.lb_aud.setText(T.STATE["audio"])
        self.lb_heard.setText(T.STATE["heard"] or "—")
        if self.pending and not T.RUN["on"]:
            d, v = self.pending
            self.pending = None
            T.save_config()
            updater.apply_and_exit(d, v)
        pf = T.STATE.get("profile")
        if pf:
            self.lb_prof.setText("الملف المستخدم: " + pf + ((" — " + T._prof.get("note", "")) if T._prof.get("note") else ""))

    def closeEvent(self, e):
        T.save_config()
        if hasattr(self, "tray"):
            self.tray.hide()
        self.overlay.hide()
        self.region.hide()
        e.accept()
        QtWidgets.QApplication.quit()
        os._exit(0)  # الخيوط الخلفية (الصوت/النماذج) ما تقفل بهدوء


def main():
    if sys.stdout is None or os.environ.get("ASOBI_LOG"):  # تشغيل بدون نافذة أوامر
        log = open(T.BASE / "app.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    if CFG["update"]["auto_check"]:
        st = updater.staged()
        if st:  # تحديث منزّل ومتحقق منه من الجلسة السابقة: نركّبه الحين قبل ما تفتح الواجهة
            updater.apply_and_exit(*st)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS.replace("CHECK", CHECK))
    try:  # أيقونة التطبيق بشريط المهام بدل أيقونة بايثون
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AsobiTranslator.App")
    except Exception:
        pass
    if ICON.exists():
        app.setWindowIcon(QtGui.QIcon(str(ICON)))
    panel = Panel()
    panel.show()
    try:
        import keyboard
        keyboard.add_hotkey("ctrl+alt+q", panel.quit_req.emit)
        keyboard.add_hotkey("ctrl+alt+h", panel.toggle_req.emit)
        keyboard.add_hotkey("ctrl+alt+m", panel.mode_req.emit)
        keyboard.add_hotkey("ctrl+alt+p", panel.front_req.emit)
    except Exception:
        pass
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
