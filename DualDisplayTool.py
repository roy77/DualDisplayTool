import ctypes
import numpy as np
import time
import sys
from PyQt5.QtWidgets import QApplication, QWidget,QVBoxLayout,QLabel,QPushButton,QFrame,QColorDialog
from PyQt5.QtCore import Qt,pyqtSignal,QPoint,QRect,QEventLoop
from PyQt5.QtGui import QGuiApplication,QPixmap,QImage,QIcon,QPainter,QPen,QColor,QPolygon,QFont,QFontMetrics,QCursor
from PyQt5.QtSvg import QSvgRenderer
from enum import Enum


class WinDLL():
    SDC_APPLY = 0x00000080
    SDC_TOPOLOGY_CLONE = 0x00000002
    SDC_TOPOLOGY_EXTEND = 0x00000004

    @staticmethod
    def extend():
        SetDisplayConfig = ctypes.windll.user32.SetDisplayConfig
        SetDisplayConfig.argtypes = [ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        SetDisplayConfig.restype = ctypes.c_long
        SetDisplayConfig(0, None, 0, None, WinDLL.SDC_TOPOLOGY_EXTEND | WinDLL.SDC_APPLY)
    
    @staticmethod
    def clone():
        SetDisplayConfig = ctypes.windll.user32.SetDisplayConfig
        SetDisplayConfig.argtypes = [ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        SetDisplayConfig.restype = ctypes.c_long
        SetDisplayConfig(0, None, 0, None, WinDLL.SDC_TOPOLOGY_CLONE | WinDLL.SDC_APPLY)

    @staticmethod
    def noSleep():
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000002)
    
    @staticmethod
    def allowSleep():
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


class Canvas(QLabel):
    class Mode(Enum):
        DRAW = 1
        ERASE = 2
        SCREENSHOT = 3

    def __init__(self,parent,size):
        super().__init__(parent)
        self.objectsArray=[]
        self.objectsArray.append({
            "pen":QPen(),
            "pos":QPolygon([])
        })
        self.pixmapIndex=0
        self.parent=parent
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.01);")
        self.width_base=min(size.width(),size.height())/200
        self.pixmap = QPixmap(size)
        self.basePixmap = QPixmap(size)
        self.basePixmap.fill(Qt.transparent)
        self.screenshotPixmap=None
        self.pixmap.fill(Qt.transparent)
        self.setPixmap(self.pixmap)
        self.setMouseTracking(True)
        self.last_mouse_position = QPoint()
        self.mode = self.Mode.DRAW
        self.pen_color = Qt.GlobalColor.red
        self.pen_width = self.width_base
        self.scale=1
        self.mode.Old=self.Mode.DRAW

    # Tracking mouse events
    def mouseMoveEvent(self,event):
        if(self.parent.parent.geometry().contains(event.pos())):
            self.parent.parent.activate()

        if (event.buttons() and Qt.MouseButton.LeftButton):
            self.draw(event.pos())

    def mousePressEvent(self,event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_position = event.pos()
            if self.mode == self.Mode.SCREENSHOT:
                self.screenshotPixmap=self.parent.window().windowHandle().screen().grabWindow(0)
            elif self.mode==self.Mode.DRAW:
                self.addObject({
                    "pen":QPen(self.pen_color,self.pen_width*self.scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin),
                    "pos":QPolygon([])
                    })
                self.drawArea= int(self.pen_width*self.scale)+5
                self.painter = QPainter(self.pixmap)
                self.painter.setPen( self.objectsArray[-1]["pen"])

                self.draw(self.last_mouse_position)

    def addObject(self,object):
        self.objectsArray=self.objectsArray[0:self.pixmapIndex+1]  
        self.objectsArray.append(object)
        if(len(self.objectsArray)>50):
            self.objectsArray.pop(0)
        self.pixmapIndex=len(self.objectsArray)-1

    def mouseReleaseEvent(self,event):
        if self.mode == self.Mode.SCREENSHOT:
            area=self.RectFromPoints(self.last_mouse_position,event.pos())         
            clipboard = QGuiApplication.clipboard()
            clipboard.setPixmap(self.screenshotPixmap.copy(area))
            self.changePixmap()
            self.update()
            self.mode=self.modeOld
            self.parent.screenshotEnd()
            QApplication.restoreOverrideCursor()
            del self.screenshotPixmap
        elif self.mode==self.Mode.DRAW:
            self.painter.end()
            self.update()

    def draw(self,points):
        if self.mode == self.Mode.DRAW:
            #self.painter.drawPoint(points)
            self.painter.drawLine(self.last_mouse_position,points)
            self.update(QRect(self.last_mouse_position, points).normalized().adjusted(-self.drawArea, -self.drawArea, self.drawArea, self.drawArea))
            self.last_mouse_position = points
            self.objectsArray[-1]["pos"].append(points)
        elif self.mode == self.Mode.ERASE:
            [start,stop]=self.currentVisibleObjects()
            res=[]
            for i in range(*[start,stop]):
                for point2 in self.objectsArray[i]["pos"]:
                    if(abs(point2.x()-points.x())+abs(point2.y()-points.y())<=25): 
                        res.append(self.objectsArray[i])
                        break
            self.pixmapIndex-=len(res)
            for ele in res: self.objectsArray.remove(ele)
            self.changePixmap()
            self.update()
        elif self.mode == self.Mode.SCREENSHOT:
            self.changePixmap()
            painter = QPainter(self.pixmap)
            painter.setPen(QPen(QColor(255, 0, 0), self.width_base/2, Qt.DashLine))
            painter.drawRect(self.RectFromPoints(self.last_mouse_position,points))
            self.update()

    def undo(self):
        if(self.pixmapIndex>0): 
            self.pixmapIndex-=1
            self.changePixmap()
            self.update()

    def redo(self):
        if(self.pixmapIndex<len(self.objectsArray)-1):
            self.pixmapIndex+=1
            self.changePixmap()
            self.update()

    def currentVisibleObjects(self):
        start=0
        for i in range(self.pixmapIndex , -1, -1):
            if self.objectsArray[i]["pen"] is None:
                start=i
                break
        return [start,self.pixmapIndex+1]

    def changePixmap(self):
        try:
            self.pixmap=self.basePixmap.copy()
            painter = QPainter(self.pixmap)
            for i in range(*self.currentVisibleObjects()):             
                pen=self.objectsArray[i]["pen"]
                if(pen is not None):
                    painter.setPen(pen)
                    if(len(self.objectsArray[i]["pos"])==1):
                        painter.drawLine(self.objectsArray[i]["pos"][0],self.objectsArray[i]["pos"][0])
                    else: painter.drawPolyline(self.objectsArray[i]["pos"])
        except Exception as err:
            print(Exception, err)
            pass

    @staticmethod
    def RectFromPoints(pt1,pt2):
        x = min(pt1.x(), pt2.x())
        y = min(pt1.y(), pt2.y())
        w = abs(pt1.x() - pt2.x())
        h = abs(pt1.y() - pt2.y())
        return QRect(x,y,w,h)

    def paintEvent(self,event):
        painter = QPainter(self)
        target_rect = event.rect()
        painter.drawPixmap(target_rect, self.pixmap, target_rect)
        painter.end()

    def lineWidth(self,value):
        if value>0: self.scale=1.5*self.scale
        else:  self.scale=1/1.5*self.scale
        return "{:.2f}".format(self.scale)
    
    def setColor(self,color):
        self.pen_color=color

    def erase(self):
        self.pixmap.fill(QColor(0, 0, 0, 0))
        self.addObject({
            "pen":None,
            "pos":QPolygon([])
        })
        self.update()
    
    def eraseMode(self):
        self.mode=self.Mode.ERASE

    def paintMode(self):
        self.mode=self.Mode.DRAW

    def screenshot(self):
        self.modeOld=self.mode
        self.mode=self.Mode.SCREENSHOT
        QApplication.setOverrideCursor(Qt.CrossCursor)

class TransparentWidget(QWidget):
    def __init__(self, parent,transparent=True):
        super().__init__()
        self.parent=parent
        self.original_flags=Qt.WindowType.FramelessWindowHint
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.00001);")
        self.setWindowOpacity(1)

        self.transparent=transparent
        self.setFlags()

    def keyPressEvent(self, event):
        self.parent.btntogglePaint.setChecked(False)
        self.parent.btntoggleErase.setChecked(False)
        self.setMode(True, False) # Paint True, State False
        QApplication.restoreOverrideCursor()
            
        super().keyPressEvent(event)

    def setScreen(self):
        screen_geometry = self.parent.window().windowHandle().screen().geometry()
        self.setGeometry(screen_geometry)
        layout=QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.canvas=Canvas(self,screen_geometry.size())
        self.layout().addWidget(self.canvas)

        self.showFullScreen()
 
    @staticmethod
    def getCursor(name,size,posY,posX):
        renderer = QSvgRenderer(name)
        pixmap = QPixmap(size,size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QCursor(pixmap,posX,posY)


    def setFlags(self):
        if self.transparent:
            self.setWindowFlags(self.original_flags | Qt.WindowTransparentForInput|Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.original_flags|Qt.WindowStaysOnTopHint)

    def setMode(self,paint,state):
            self.transparent = not state
            if(self.transparent): 
                QApplication.setOverrideCursor(Qt.ArrowCursor)
            else: 
                if(paint):
                    QApplication.setOverrideCursor(self.getCursor("Icons/paintbrush.svg",100,100,0))
                else:
                    QApplication.setOverrideCursor(self.getCursor("Icons/eraser.svg",100,0,50))
            if(paint): self.canvas.paintMode()
            else: self.canvas.eraseMode()
            
            self.setFlags()
            self.show()
            self.parent.activate()

    def getCanvas(self):
        return self.canvas
    
    def screenshot(self):
        self.transparentOld=self.transparent
        self.transparent=False
        self.setFlags()
        self.show()
        self.canvas.screenshot()
    
    def screenshotEnd(self):
        self.transparent=self.transparentOld
        self.setFlags()
        self.show()



class OverlayWindow(QWidget):
    onlyOneScreeenSignal = pyqtSignal()

    def __init__(self,parent):
        super().__init__()
        self.layout = QVBoxLayout()
        self.parent=parent

        self.setStyleSheet("background-color: black;")
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        
        self.thread = None
                    
    def disable(self):
        self.hide()

    def maximize(self,screen):
        self.setGeometry(screen.geometry())
        self.showFullScreen()
        #self.showNormal()
        #self.showFullScreen() # Für Vollbild
        #self.showMaximized() # Für maximiertes Fenster

    def pause(self,screen,pixmap):
        pixmap = pixmap.scaled(screen.geometry().size(), Qt.KeepAspectRatio) 
        self.label.setPixmap(pixmap)
        self.maximize(screen)

    def black(self,screen):
        size=screen.size()
        h,w=(size.height(),size.width())
        
        pixmap = QPixmap.fromImage(QImage(np.zeros(h*w*3,dtype=np.uint8).data, w, h, 3*w, QImage.Format_RGB888))
        self.label.setPixmap(pixmap)
        self.maximize(screen)

    def moveEvent(self, event):
        screen_geometry = self.parent.window().windowHandle().screen().geometry()
        if(screen_geometry.contains(event.pos())):
            self.onlyOneScreeenSignal.emit()

        super().moveEvent(event)

class VerticalLabel(QLabel):
    def __init__(self, text,size):
        super().__init__()
        self.setWordWrap(True)
        self.text = text
        self.setMinimumSize(size, 2*size)

    def paintEvent(self, event):
        painter = QPainter(self)
        font=QFont("Arial", 12)
        painter.setFont(font)
        h=QFontMetrics(font).boundingRect(self.text).height()

        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(-90)
        painter.drawText(int(-self.height() / 2),int(self.width() / 2-h/2), self.text) 


class ButtonWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)

        self.transWindow=TransparentWidget(self)
        self.cloneWindow=None
        self.offset=None
        
        # Create a layout for the buttons
        self.layout = QVBoxLayout()
        self.m_drag=False
        self.layout.setSpacing(3)

        self.btnsize=80
        start_position = self.pos() #Abrufen der Startposition
        for screen in QApplication.screens():
            screen_geometry = screen.geometry()
            if screen_geometry.contains(start_position):
                self.btnsize=int(min(screen_geometry.width(),screen_geometry.height())/32)
                self.move(0,int((screen_geometry.height()-self.btnsize*18)/2))
   
        self.btnClose=self.addButton("window-close.svg",False,self.button_close,"Close")
        self.addSeperator()
        self.btnClone=self.addButton("eye.svg",True,self.setClone,"Screen Clone")
        self.btnPause=self.addButton("pause-window.svg",True,self.setPause,"Screen Pause")
        self.btnBlack=self.addButton("black-large-square.svg",True,self.setBlack,"Screen Black")
        self.btnDisable=self.addButton("eye-off.svg",True,self.setDisable,"Screen normal",True)
        self.addSeperator()        
        self.btnNoSleep=self.addButton("sleeping-face.svg",True,self.toggleSleep,"Toggle Don´t Sleep",True)
        self.addSeperator()
        self.btntogglePaint=self.addButton("paintbrush.svg",True,self.togglePaintMode,"Draw on Screen",False)
        self.lblWidth=self.addLabel("1","Line Width")
        self.addButton("thicker.svg",False,self.lineWidthUp,"Line Thicker")
        self.addButton("thinner.svg",False,self.lineWidthDown,"Line Thinner")
        self.addButton("palette.svg",False,self.setColor,"Set Color")
        self.btntoggleErase=self.addButton("clear.svg",True,self.toggleEraseMode,"Erase Lines",False)
        self.addButton("erasescreen.svg",False,self.erase,"Erase All")
        self.addButton("undo.svg",False,self.undo,"Undo")
        self.addButton("redo.svg",False,self.redo,"Redo")
        self.addSeperator()
        self.addButton("screenshot.svg",False,self.screenshot,"Screenshot")

        self.addSeperator()
        label = VerticalLabel("©Heintz",self.btnsize)
        self.layout.addWidget(label)

        
        self.toggleSleep(True)

        self.setLayout(self.layout)

    def toggleEraseMode(self,state):
        if(state):
            self.btntogglePaint.setChecked(False)
        self.transWindow.setMode(False,state)
    
    def togglePaintMode(self,state):
        if(state):
            self.btntoggleErase.setChecked(False)
        self.transWindow.setMode(True,state)


    def undo(self):
        self.transWindow.getCanvas().undo()
    
    def redo(self):
        self.transWindow.getCanvas().redo()

    def screenshot(self):
        self.transWindow.screenshot()

    def erase(self):
        self.transWindow.getCanvas().erase()

    def eraseLines(self):
        self.transWindow.getCanvas().eraseLines()

    def setColor(self):
        self.transWindow.getCanvas().setColor(QColorDialog.getColor(parent=self))

    def lineWidthUp(self):
        value=self.transWindow.getCanvas().lineWidth(1)
        self.lblWidth.setText(value)

    def lineWidthDown(self):
        value=self.transWindow.getCanvas().lineWidth(-1)
        self.lblWidth.setText(value)
        
    def showEvent(self, event):
        super().showEvent(event)

        if(self.cloneWindow is None):
            self.transWindow.setScreen()
            self.cloneWindow=OverlayWindow(self)
            self.cloneWindow.onlyOneScreeenSignal.connect(lambda: self.onlyOneScreen())
            if(self.getScreenCount()==2):
                self.setDisable()
            else: self.setClone()


    def activate(self):
        if(not self.isActiveWindow()): self.activateWindow()

    def addSeperator(self):
        separator = QFrame(self)
        separator.setLineWidth(3)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken) 
        self.layout.addWidget(separator)
        self.layout.addWidget(separator)
        self.layout.addWidget(separator)

    def addButton(self,image,toggle,call,tip,toggleState=False):
        button = QPushButton()
        button.setFixedSize(self.btnsize, self.btnsize)
        button.setIcon(QIcon("Icons/"+image))
        button.setCheckable(toggle)
        button.setChecked(toggleState)
        button.setToolTip(tip)
        button.clicked.connect(call)
        self.layout.addWidget(button)
        return button

    def addLabel(self,text,tip):
        label = QLabel()
        label.setText(text)
        label.setToolTip(tip)
        label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(label)
        return label

    def button_close(self):
        sys.exit(app.exec_())
    
    def getScreenCount(self):
        return len(QGuiApplication.screens())
    
    def onlyOneScreen(self):
        self.setClone()

    def setClone(self):
        if(self.getScreenCount()==2):
            WinDLL.clone()
            self.cloneWindow.disable()
        self.btnClone.setChecked(True)
        self.btnPause.setChecked(False)
        self.btnBlack.setChecked(False)
        self.btnDisable.setChecked(False)

    def setBlack(self):
        if(self.getScreenCount()==1):
            WinDLL.extend()
            if(not self.waitForSwitch()):
                self.btnClone.setChecked(True)
                self.btnBlack.setChecked(False)
                return
        self.cloneWindow.black(self.getSecondScreen())
        self.btnClone.setChecked(False)
        self.btnPause.setChecked(False)
        self.btnBlack.setChecked(True)
        self.btnDisable.setChecked(False)

    def setDisable(self):
        if(self.getScreenCount()==1):
            WinDLL.extend()
            if(not self.waitForSwitch()):
                self.btnClone.setChecked(True)
                self.btnDisable.setChecked(False)
                return
        self.cloneWindow.disable()
        self.btnClone.setChecked(False)
        self.btnPause.setChecked(False)
        self.btnBlack.setChecked(False)
        self.btnDisable.setChecked(True)

    def getSecondScreen(self):
        screens = QGuiApplication.screens()
        for screen in screens:
            if screen != self.window().windowHandle().screen():
                return screen
        return None

    def waitForSwitch(self):
        loop=35
        screen=None
        while(screen is None and loop>0):
            time.sleep(0.05)
            screen=self.getSecondScreen()
            QEventLoop().processEvents()
            loop-=1
        return (loop!=0)       

    def setPause(self):
        pixmap=self.window().windowHandle().screen().grabWindow(0)
        if(self.getScreenCount()==1):
            WinDLL.extend()
            if(not self.waitForSwitch()):
                self.btnPause.setChecked(False)
                return
        self.cloneWindow.pause(self.getSecondScreen(),pixmap)
        self.btnClone.setChecked(False)
        self.btnPause.setChecked(True)
        self.btnBlack.setChecked(False)
        self.btnDisable.setChecked(False)

    def toggleSleep(self,checked):
        if(checked): WinDLL().noSleep()
        else: WinDLL().allowSleep()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.offset = event.globalPos()-self.pos()

    def mouseMoveEvent(self, event):
        if self.offset is not None:
            self.move(event.globalPos() - self.offset)

    def mouseReleaseEvent(self, event):
        self.offset=None


app = QApplication(sys.argv)

window = ButtonWidget()
window.show()

sys.exit(app.exec_())
