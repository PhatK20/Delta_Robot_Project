import sys
from PyQt6.QtGui import QImage, QPixmap, QGuiApplication
# from PyQt6.QtCore import QThread, QObject, pyqtSignal
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QDialog
from PyQt6.uic import loadUi
import serial.tools.list_ports
import DeltaKinematic_v3 as Delta
import numpy as np
import cv2

class MyMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Load the user interface from the .ui file
        loadUi("Gui_Delta/DeltaRobot_v2.ui", self)
        self.setWindowTitle("Delta robot control interface")
        self.program_started = False
        self.connected = False
        self.selected_port = None
        self.ser = None
        self.send_data = None
        self.string = None

        self.init_connect_FK()
        self.init_connect_IK()
        self.init_connect_control()
        self.init_connect_setup_com_port()
        self.init_connect_camera()


    def init_connect_FK(self):
        self.pushButton_FK.clicked.connect(self.calculate_FK)

    def init_connect_IK(self):
        self.pushButton_IK.clicked.connect(self.calculate_IK)

    def init_connect_control(self):
        self.pushButton_run.clicked.connect(self.run)
        self.pushButton_stop.clicked.connect(self.stop)
        self.pushButton_reset.clicked.connect(self.reset)
        self.pushButton_setHome.clicked.connect(self.setHome)

    def init_connect_setup_com_port(self):
        self.populate_com_ports()
        self.pushButton_connect.clicked.connect(self.connect_com_port)
        self.pushButton_disconnect.clicked.connect(self.disconnect_com_port)

    def init_connect_camera(self):
        self.black_pixmap = None  # Thêm biến để lưu pixmap màu đen
        self.create_black_pixmap()  # Gọi hàm để tạo pixmap màu đen
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.camera = cv2.VideoCapture(1)

        self.pushButton_on_camera.clicked.connect(self.on_camera)
        self.pushButton_off_camera.clicked.connect(self.off_camera)

    def init_setup(self):
        self.theta1 = 0
        self.theta2 = 0
        self.theta3 = 0
        self.theta1_previous = 0
        self.theta2_previous = 0
        self.theta3_previous = 0 
        self.bottle = 0
        self.can = 0
        self.lineEdit_theta1.setText(str(self.theta1))
        self.lineEdit_theta2.setText(str(self.theta2))
        self.lineEdit_theta3.setText(str(self.theta3))
        self.lineEdit_counter_bottle.setText(str(self.bottle))
        self.lineEdit_counter_can.setText(str(self.can))
        positions = Delta.Forward_Kinematic(self.theta1, self.theta2, self.theta3)
        self.Px = positions[1]
        self.Py = positions[2]
        self.Pz = positions[3]
        self.lineEdit_Px.setText(str(self.Px))
        self.lineEdit_Py.setText(str(self.Py))
        self.lineEdit_Pz.setText(str(self.Pz))
    
    def calculate_theta_ref(self):
        self.theta1_ref = self.theta1 - abs(self.theta1_previous)
        self.theta2_ref = self.theta2 - abs(self.theta2_previous)
        self.theta3_ref = self.theta3 - abs(self.theta3_previous)
        
    def create_black_pixmap(self):
        # Tạo một pixmap màu đen với kích thước 640x480
        black_image = np.zeros((480, 640, 3), dtype=np.uint8)
        black_image.fill(0)  # Điền màu đen vào ảnh
        black_image = cv2.cvtColor(black_image, cv2.COLOR_BGR2RGB)
        black_qimage = QImage(black_image.data, black_image.shape[1], black_image.shape[0], QImage.Format.Format_RGB888)
        self.black_pixmap = QPixmap.fromImage(black_qimage)

    def update_frame(self):
        ret, frame = self.camera.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = QImage(frame.data, frame.shape[1], frame.shape[0], QImage.Format.Format_RGB888)
            self.label_camera.setPixmap(QPixmap.fromImage(frame))

    def on_camera(self):
        if not self.timer.isActive():
            self.timer.start(16)  # 16 ms là khoảng thời gian giữa các khung hình
            self.pushButton_on_camera.setEnabled(False)
            self.pushButton_off_camera.setEnabled(True)

    def off_camera(self):
        if self.timer.isActive():
            self.timer.stop()
            self.pushButton_on_camera.setEnabled(True)
            self.pushButton_off_camera.setEnabled(False)
            self.label_camera.setPixmap(self.black_pixmap)

    def process_send_data(self, output_string):
        self.send_data = output_string
        self.ser.write(self.send_data.encode())
        self.lineEdit_sent_data.setText(output_string)
        length = len(output_string) * self.dataBits / 8
        self.lineEdit_sent_length.setText(str(length))

    def format_number(self, num):
        sign = '-' if num < 0 else '+'
        num_str = str(abs(num)).zfill(4)
        return f"{sign}{num_str}"

    def string_value(self, num1, num2, num3):
        for_num1 = self.format_number(num1)
        for_num2 = self.format_number(num2)
        for_num3 = self.format_number(num3)
        return f"{for_num1}a{for_num2}b{for_num3}c+0000d"
    
    def create_padded_string(self):
        if len(self.string) < 24:
        # Nếu chuỗi không đủ 24 ký tự, thêm dấu cách vào sau chuỗi
            self.string += ' ' * (24 - len(self.string))
          
        
    def calculate_FK(self):
        if self.program_started:
            input_theta1 = int(self.lineEdit_theta1.text())
            input_theta2 = int(self.lineEdit_theta2.text())
            input_theta3 = int(self.lineEdit_theta3.text())
            if all(0 <= input_theta <= 90 for input_theta in (input_theta1, input_theta2, input_theta3)):
                self.theta1 = input_theta1
                self.theta2 = input_theta2
                self.theta3 = input_theta3
                self.calculate_theta_ref()
                self.theta1_previous = self.theta1
                self.theta2_previous = self.theta2
                self.theta3_previous = self.theta3
                positions = Delta.Forward_Kinematic(self.theta1, self.theta2, self.theta3)
                self.Px = positions[1]
                self.Py = positions[2]
                self.Pz = positions[3]
                self.lineEdit_Px.setText(str(self.Px))
                self.lineEdit_Py.setText(str(self.Py))
                self.lineEdit_Pz.setText(str(self.Pz))
            
                self.process_send_data(self.string_value(self.theta1_ref, self.theta2_ref, self.theta3_ref))
            
            else:
                warning_dialog.show()


    def calculate_IK(self):
        if self.program_started:
            self.Px = float(self.lineEdit_Px.text())
            self.Py = float(self.lineEdit_Py.text())
            self.Pz = float(self.lineEdit_Pz.text())
            theta = Delta.Inverse_Kinematic(self.Px, self.Py, self.Pz)
            self.theta1 = int(theta[1])
            self.theta2 = int(theta[2])
            self.theta3 = int(theta[3])
            self.calculate_theta_ref()
            self.theta1_previous = self.theta1
            self.theta2_previous = self.theta2
            self.theta3_previous = self.theta3
            self.lineEdit_theta1.setText(str(self.theta1))
            self.lineEdit_theta2.setText(str(self.theta2))
            self.lineEdit_theta3.setText(str(self.theta3))
            
            self.process_send_data(self.string_value(self.theta1_ref, self.theta2_ref, self.theta3_ref))

    def run(self):
        self.program_started = True
        self.string = 'Run'
        self.create_padded_string()
        self.process_send_data(self.string)
        print("Program started")

    def stop(self):
        self.program_started = False
        self.string = 'Stop'
        self.create_padded_string()
        self.process_send_data(self.string)
        print("Program stopped")

    def reset(self):
        if self.program_started:
            self.lineEdits = [
                self.lineEdit_sent_data,
                self.lineEdit_sent_length,
                self.lineEdit_theta1,
                self.lineEdit_theta2,
                self.lineEdit_theta3,
                self.lineEdit_Px,
                self.lineEdit_Py,
                self.lineEdit_Pz,
            ]
        for lineEdit in self.lineEdits:
            lineEdit.clear()

        self.string = 'Reset'
        self.create_padded_string()
        self.process_send_data(self.string)

    def setHome(self):
        if self.program_started:
            self.theta1 = 0
            self.theta2 = 0
            self.theta3 = 0
            self.lineEdit_theta1.setText(str(self.theta1))
            self.lineEdit_theta2.setText(str(self.theta2))
            self.lineEdit_theta3.setText(str(self.theta3))
            self.calculate_FK()

            self.string = 'Home'
            self.create_padded_string()
            self.process_send_data(self.string)

    def populate_com_ports(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.comboBox_comPort.addItem(port.device)

    def connect_com_port(self):
        if not self.connected:
            self.selected_port = self.comboBox_comPort.currentText()
            baudrate = int(self.comboBox_baudRate.currentText())
            self.dataBits = int(self.comboBox_dataBits.currentText())
            parity_string = self.comboBox_parity.currentText()
            if parity_string == "None":
                parity = serial.PARITY_NONE
            elif parity_string == "Even":
                parity = serial.PARITY_EVEN
            else:
                parity = serial.PARITY_ODD
            stopBits = float(self.comboBox_stopBits.currentText())
            try:
                # Thực hiện kết nối đến cổng COM
                self.ser = serial.Serial(
                    self.selected_port, baudrate, self.dataBits, parity, stopBits
                )
                self.connected = True
                self.label_state.setText("ON")
                self.init_setup()
                print(f"Connected to {self.selected_port} at {baudrate} baud")
            except Exception as e:
                print(f"Error connecting to {self.selected_port}: {str(e)}")
        else:
            print("Already connected to a COM port.")

    def disconnect_com_port(self):
        if self.connected:
            self.ser.close()
            self.connected = False
            self.label_state.setText("OFF")
            print(f"Disconnected from {self.selected_port}")
        else:
            print("Not connected to any COM port.")

    def show(self):
        super().show()
        # Get the rectangle representing the window
        qr = self.frameGeometry()
        # Get the center point of the screen
        cp = QGuiApplication.primaryScreen().availableGeometry().center()
        # Move the rectangle's center point to the screen's center point
        qr.moveCenter(cp)
        # Move the window to the rectangle's top left point
        self.move(qr.topLeft())

class MessageDialog(QDialog):
    def __init__(self):
        super().__init__()
        loadUi("Gui_Delta/warning_v1.ui", self)
        self.setWindowTitle('Warning Dialog')
        self.pushButton_ok.clicked.connect(self.close)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MyMainWindow()
    warning_dialog = MessageDialog()
    main_window.show()
    sys.exit(app.exec())
