"""يرسم أيقونة البرنامج (assets/icon.png و icon.ico). يُشغَّل مرة وحدة: python make_icon.py"""
import os
import struct
import sys
from pathlib import Path

pass
from PySide6 import QtCore, QtGui, QtWidgets

OUT = Path(__file__).resolve().parent / "assets"


def draw(size):
    img = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    img.fill(0)
    p = QtGui.QPainter(img)
    p.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing | QtGui.QPainter.SmoothPixmapTransform)
    s = size / 256.0
    p.scale(s, s)
    # خلفية متدرجة بزوايا مدوّرة
    g = QtGui.QLinearGradient(0, 0, 256, 256)
    g.setColorAt(0, QtGui.QColor("#6d5dfc"))
    g.setColorAt(1, QtGui.QColor("#16b8f3"))
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QtCore.QRectF(8, 8, 240, 240), 56, 56)
    # فقاعة كلام بيضاء
    bub = QtGui.QPainterPath()
    bub.addRoundedRect(QtCore.QRectF(46, 56, 164, 112), 34, 34)
    tail = QtGui.QPainterPath()
    tail.moveTo(86, 160)
    tail.lineTo(80, 204)
    tail.lineTo(126, 166)
    tail.closeSubpath()
    p.setBrush(QtGui.QColor(255, 255, 255, 245))
    p.drawPath(bub.united(tail))
    # حرف ع في الفقاعة
    f = QtGui.QFont("Segoe UI", 1)
    f.setFamilies(["Segoe UI", "Tahoma", "Arial"])
    f.setPixelSize(84)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QtGui.QColor("#4a3fd8"))
    p.drawText(QtCore.QRectF(46, 34, 164, 120), QtCore.Qt.AlignCenter, "ع")
    # نقطتا صوت صغيرتان
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(QtGui.QColor(255, 255, 255, 235))
    for i, r in enumerate((9, 9, 9)):
        p.drawEllipse(QtCore.QPointF(150 + i * 24, 206), r, r)
    p.end()
    return img


def png_bytes(img):
    ba = QtCore.QByteArray()
    buf = QtCore.QBuffer(ba)
    buf.open(QtCore.QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def main():
    QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    OUT.mkdir(exist_ok=True)
    draw(512).save(str(OUT / "icon.png"))
    sizes = [16, 24, 32, 48, 64, 128, 256]
    data = [png_bytes(draw(n)) for n in sizes]
    head = struct.pack("<HHH", 0, 1, len(sizes))
    off = 6 + 16 * len(sizes)
    ent = b""
    for n, d in zip(sizes, data):
        ent += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(d), off)
        off += len(d)
    (OUT / "icon.ico").write_bytes(head + ent + b"".join(data))
    print("ok", OUT)




def make_check():
    QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    img = QtGui.QImage(36, 36, QtGui.QImage.Format_ARGB32)
    img.fill(0)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    pen = QtGui.QPen(QtGui.QColor("white"), 4.5, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
    p.setPen(pen)
    p.drawPolyline([QtCore.QPointF(9, 19), QtCore.QPointF(15, 25), QtCore.QPointF(27, 11)])
    p.end()
    img.save(str(OUT / "check.png"))


if __name__ == "__main__":
    main()
    make_check()
