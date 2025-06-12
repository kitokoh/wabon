import csv
import os
import sys
import re
import sqlite3
import xlrd
import requests
import time
import json
import logging # Added for fallback logging
from PyQt5.QtGui import QBrush, QTextCursor, QColor, QRegExpValidator, QIcon, QPixmap, QFontDatabase, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint, QRegExp, QAbstractTableModel
from PyQt5.QtSql import QSqlDatabase, QSqlQueryModel, QSqlQuery, QSqlError # Added QSqlError
from pytz import timezone
from jdatetime import datetime as dt
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QDialog, QDesktopWidget
from wasender import Ui_MainWindow
import icons_rc
from browserCtrl import Web
from src import dpi
from appLog import log


class Main():

    def __init__(self):
        super(Main, self).__init__()
        app = QApplication(sys.argv)
        self.__LICENS__ = True
        self.__VERSION__ = '1.0'
        self.cv = 0
        self.Net = None
        self.User = True
        log.info(fr"===== Program Runing {self.__VERSION__} =====")
        self.insert = NetWork(version=self.__VERSION__) # Assuming NetWork handles its own startup errors
        try:
            self.insert.start()
        except Exception as e: # Should be QThread.start specific if possible
            log.error(f"Failed to start 'insert' NetWork thread: {e}")
            # Decide if this is critical enough to stop app init
        # self.insert.Checker.connect(self.qthreadInsert) # This was commented out
        self.userChck() # Updated to handle errors

        self.MainWindow = myQMainWindow()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self.MainWindow)
        self.MainWindow.center()

        # Ensure 'temp' directory exists early
        try:
            os.makedirs('temp', exist_ok=True)
            log.debug("Ensured 'temp' directory exists.")
        except OSError as e:
            log.error(f"Could not create 'temp' directory: {e}")
            # This could be critical, an early msgError or sys.exit might be needed if 'temp' is essential.
            # For now, we'll let it proceed and potentially fail later if dbPath can't be established.

        # Font Loading
        font_db2 = QFontDatabase()
        font_path = os.path.join("fonts", "MesloLGS NF.ttf")
        font_id2 = font_db2.addApplicationFont(font_path)
        if font_id2 == -1:
            log.warning(f"Failed to load font: {font_path}. Font file might be missing or corrupt.")
        else:
            font_families = QFontDatabase.applicationFontFamilies(font_id2)
            if font_families:
                log.debug(f"Successfully loaded application font: {font_path}. Families: {font_families}")
            else: # Should not happen if font_id2 is valid, but good for robustness
                log.warning(f"Loaded application font {font_path} but no families found.")
        # QFontDatabase.applicationFontFamilies(font_id2) # This line was fine, but result can be used for log

        # Translations Loading
        translations_path = os.path.join(".", "src", "lang", "translations.json")
        try:
            with open(translations_path, "r", encoding="utf8") as f:
                self.lang = json.load(f)
            log.info(f"Translations loaded successfully from {translations_path}")
        except FileNotFoundError:
            log.error(f"{translations_path} not found. Application will use a basic English fallback.")
            self.lang = { # Basic fallback structure
                "translatables": { "msgerr_ok": {"English": "OK"}, # Essential for msgError
                                   "app_name_lbl": {"English": "WA Sender"} # Example for window title
                                 }, "languages": ["English"] }
            # A more comprehensive fallback would list all keys used in languageSet to prevent KeyErrors
            # For now, languageSet's try-except blocks will handle individual missing keys.
        except json.JSONDecodeError as e:
            log.error(f"Error decoding {translations_path}: {e}. Using basic English fallback.")
            self.lang = { "translatables": { "msgerr_ok": {"English": "OK"}}, "languages": ["English"] }
        except OSError as e:
            log.error(f"OSError reading {translations_path}: {e}. Using basic English fallback.")
            self.lang = { "translatables": { "msgerr_ok": {"English": "OK"}}, "languages": ["English"] }

        self.ln = self.lang.get("translatables", {})

        # languageConf must be called AFTER self.lang is initialized
        self.languageConf()

        # Initialize self.cln (current language name)
        if self.ui.langs.count() > 0:
            self.cln = self.ui.langs.currentText()
            if not self.cln and self.lang.get("languages"): # If currentText is somehow empty initially
                self.cln = self.lang["languages"][0]
                self.ui.langs.setCurrentText(self.cln) # Try to set it in UI too
            elif not self.cln: # Ultimate fallback for self.cln
                 self.cln = "English"
        elif self.lang.get("languages"):
            self.cln = self.lang["languages"][0]
        else:
            self.cln = "English" # Should not happen if fallback self.lang is correct
        log.info(f"Initial language set to: {self.cln}")

        self.dbPath = os.path.join("temp", "temporary.data")
        self.reviewedCount = 0
        self.MainWindow.setWindowFlags(self.MainWindow.windowFlags() | Qt.FramelessWindowHint)
        self.MainWindow.setAttribute(Qt.WA_TranslucentBackground)
        self.ui.btn_close.clicked.connect(self.MainWindow.close)
        self.ui.btn_maxmin.clicked.connect(self.maxmin)
        self.ui.btn_min.clicked.connect(self.MainWindow.showMinimized)
        self.ui.btn_export.clicked.connect(self.export)
        self.ui.btn_gnarate.clicked.connect(self.generate)
        self.ui.btn_clear.clicked.connect(self.clearList)
        self.ui.btn_img.clicked.connect(self.selectIMG)
        self.ui.lb_version.setText(self.__VERSION__)
        regex = QRegExp("^(?!0+$)[0-9]+$")
        self.validator = QRegExpValidator(regex)
        # forms init
        self.initGenerate()
        self.initImport()
        self.initAccountList()

        icon = QIcon()
        icon.addPixmap(QPixmap(":/main/icon.ico"), QIcon.Normal, QIcon.Off)
        self.MainWindow.setWindowIcon(icon)
        self.oldPos = self.MainWindow.pos()
        self.areaCode = self.ui.areaCode.text()
        self.RememberLogin = True
        self.ui.sleepMin.setValidator(self.validator)
        self.ui.sleepMin.setMaxLength(4)
        self.ui.sleepMax.setValidator(self.validator)
        self.ui.sleepMax.setMaxLength(4)
        self.p = ''
        self.ui.btn_import.clicked.connect(self.importer)
        self.ui.btn_acclist.clicked.connect(self.accountsList)
        self.ui.btn_start.clicked.connect(self.StarT)
        self.ui.btn_stop.clicked.connect(self.stop_progress)
        self.ui.LogBox.setReadOnly(True)
        self.ui.LogBox.setTextInteractionFlags(Qt.NoTextInteraction)  # non-selectable Text in QPlainTextEdit
        self.ui.langs.currentIndexChanged.connect(self.languageSet)
        self.languageSet()

        self.MainWindow.show()
        sys.exit(app.exec_())

    def languageConf(self):
        self.ui.langs.clear()
        for i, l in enumerate(self.lang["languages"]):
            self.ui.langs.addItem("")
            self.ui.langs.setItemText(i, l)
            if i == 0:
                self.ui.langs.setCurrentIndex(i)

    def languageSet(self):
        self.cln = self.ui.langs.currentText()
        log.debug(fr"change language to `{self.cln}`")
        try:
            self.ui.btn_import.setText(self.ln["btn_import"][self.cln])
            self.ui.btn_import.setToolTip(self.ln["btn_import_ttp"][self.cln])
            self.ui.btn_gnarate.setText(self.ln["btn_gnarate"][self.cln])
            self.ui.btn_gnarate.setToolTip(self.ln["btn_gnarate_ttp"][self.cln])
            self.ui.btn_export.setText(self.ln["btn_export"][self.cln])
            self.ui.btn_export.setToolTip(self.ln["btn_export_ttp"][self.cln])
            self.ui.btn_clear.setText(self.ln["btn_clear"][self.cln])
            self.ui.btn_clear.setToolTip(self.ln["btn_clear_ttp"][self.cln])
            self.ui.btn_acclist.setText(self.ln["btn_acclist"][self.cln])
            self.ui.btn_acclist.setToolTip(self.ln["btn_acclist_ttp"][self.cln])
            self.ui.btn_start.setText(self.ln["btn_start"][self.cln])
            self.ui.btn_start.setToolTip(self.ln["btn_start_ttp"][self.cln])
            self.ui.btn_stop.setText(self.ln["btn_stop"][self.cln])
            self.ui.btn_stop.setToolTip(self.ln["btn_stop_ttp"][self.cln])
            self.ui.whatsAppNumbers.setText(self.ln["whatsAppNumbers"][self.cln])
            self.ui.label_count_txt.setText(self.ln["label_count_txt"][self.cln])
            self.ui.label_count_txt_3.setText(self.ln["label_count_txt_3"][self.cln])
            self.ui.label_count_txt_4.setText(self.ln["label_count_txt_4"][self.cln])
            self.ui.label_count_txt_5.setText(self.ln["label_count_txt_5"][self.cln])
            self.ui.textBrowser.setText(self.ln["textBrowser"][self.cln])
            self.ui.start_tab.setTabText(self.ui.start_tab.indexOf(
                self.ui.tab_Analyz), self.ln["start_tab_a"][self.cln])
            self.ui.start_tab.setTabText(self.ui.start_tab.indexOf(self.ui.tab_msg), self.ln["start_tab_m"][self.cln])
            self.ui.start_tab.setTabText(self.ui.start_tab.indexOf(self.ui.tab_img), self.ln["start_tab_i"][self.cln])
            self.ui.frame_LCD_label.setToolTip(self.ln["frame_LCD_label"][self.cln])
            self.ui.frame_LCD.setToolTip(self.ln["frame_LCD"][self.cln])
            self.ui.LogBox.setToolTip(self.ln["LogBox"][self.cln])
            self.ui.frame_msg.setToolTip(self.ln["frame_msg"][self.cln])
            self.ui.tab_Analyz.setToolTip(self.ln["tab_Analyz_ttp"][self.cln])
            self.ui.btn_close.setToolTip(self.ln["btn_close"][self.cln])
            self.ui.btn_min.setToolTip(self.ln["btn_min"][self.cln])
            self.ui.btn_maxmin.setToolTip(self.ln["btn_maxmin"][self.cln])
            self.ui.label.setText(self.ln["label"][self.cln])
            self.ui.textMSG.setToolTip(self.ln["textMSG"][self.cln])
            self.ui.label_2.setText(self.ln["label_2"][self.cln])
            self.ui.label_3.setText(self.ln["label_3"][self.cln])
            self.ui.sleepMax.setToolTip(self.ln["sleepMax"][self.cln])
            self.ui.sleepMin.setToolTip(self.ln["sleepMin"][self.cln])
            self.ui.label_11.setText(self.ln["label_11"][self.cln])
            self.ui.label_10.setText(self.ln["label_10"][self.cln])
            self.ui.sleepMax_I.setToolTip(self.ln["sleepMax"][self.cln])
            self.ui.sleepMin_I.setToolTip(self.ln["sleepMin"][self.cln])
            self.ui.label_caption.setText(self.ln["label_caption"][self.cln])
            self.ui.caption.setToolTip(self.ln["caption_ttp"][self.cln])
            self.ui.btn_img.setText(self.ln["btn_img"][self.cln])
            self.ui.btn_img.setToolTip(self.ln["btn_img_ttp"][self.cln])
            self.ui.tab_msg.setToolTip(self.ln["tab_msg"][self.cln])
            self.ui.tab_img.setToolTip(self.ln["tab_img"][self.cln])
            self.ui.areaCode.setToolTip(self.ln["areaCode"][self.cln])
            self.ui.areaCode.setPlaceholderText(self.ln["areacode_hldr"][self.cln])
            self.ui.langs.setToolTip(self.ln["langs"][self.cln])
        except Exception as e:
            log.exception(f"Error applying language settings for '{self.cln}' to main UI: {e}")
        try:
            self.fia.btn_importaccount.setText(self.ln["fia_btn_importaccount"][self.cln])
            self.fia.btn_importaccount.setToolTip(self.ln["fia_btn_importaccount_ttp"][self.cln])
            self.fia.btn_addnewtel.setPlaceholderText(self.ln["fia_btn_addnewtel_phdr"][self.cln])
            self.fia.label_2.setText(self.ln["fia_label_2"][self.cln])
            self.fia.btn_import_cancel.setText(self.ln["btn_cancel"][self.cln])
            self.fia.btn_import_cancel.setToolTip(self.ln["fia_btn_import_cancel_ttp"][self.cln])
        except Exception as e:
            log.exception(f"Error applying language settings for '{self.cln}' to import account form: {e}")
        try:
            self.fi.label.setText(self.ln["fi_label"][self.cln])
            self.fi.btn_importFile.setText(self.ln["fi_btn_importFile"][self.cln])
            self.fi.btn_importFile.setToolTip(self.ln["fi_btn_importFile_ttp"][self.cln])
            self.fi.label_2.setText(self.ln["fi_label_2"][self.cln])
            self.fi.btn_importManual.setText(self.ln["fi_btn_importManual"][self.cln])
            self.fi.btn_importManual.setToolTip(self.ln["fi_btn_import_cancel_ttp"][self.cln])
            self.fi.btn_import_cancel.setText(self.ln["btn_cancel"][self.cln])
            self.fi.btn_import_cancel.setToolTip(self.ln["fi_btn_import_cancel_ttp"][self.cln])
            self.fi.manualNumber.setToolTip(self.ln["fi_manualNumber_ttp"][self.cln])
        except Exception as e:
            log.exception(f"Error applying language settings for '{self.cln}' to import number form: {e}")
        try:
            self.frOM.label.setText(self.ln["frm_label"][self.cln])
            self.frOM.label_2.setText(self.ln["frm_label_2"][self.cln])
            self.frOM.generate_num.setToolTip(self.ln["frm_generate_num"][self.cln])
            self.frOM.generate_count.setToolTip(self.ln["frm_generate_count"][self.cln])
            self.frOM.btn_g_ok.setText(self.ln["frm_btn_g_ok"][self.cln])
            self.frOM.btn_g_ok.setToolTip(self.ln["frm_btn_g_ok_ttp"][self.cln])
            self.frOM.btn_g_cancel.setText(self.ln["btn_cancel"][self.cln])
            self.frOM.btn_g_cancel.setToolTip(self.ln["frm_btn_g_cancel_ttp"][self.cln])
        except Exception as e:
            log.exception(f"Error applying language settings for '{self.cln}' to generate number form: {e}")
        # try:
        #     self.ui.retranslateUi(MainWindow=self.MainWindow)
        # except Exception as e:
        #     log.exception(f"Error in self.ui.retranslateUi: {e}")
        # try:
        #     self.fia.retranslateUi(self.formQImport)
        # except Exception as e:
        #     log.exception(f"Error in self.fia.retranslateUi: {e}")
        # try:
        #     self.fi.retranslateUi(self.formQImport1)
        # except Exception as e:
        #     log.exception(f"Error in self.fi.retranslateUi: {e}")
        # try:
        #     self.frOM.retranslateUi(self.generateForm)
        # except Exception as e:
        #     log.exception(f"Error in self.frOM.retranslateUi: {e}")

    def userChck(self):
        try:
            log.debug("Setting up user status check thread.")
            self.userStatus = NetWork(step=2, user=self.__LICENS__)
            self.userStatus.start()
            self.userStatus.Checker.connect(self.userChecker)
        except Exception as e:
            log.exception(f"Error during userChck setup or thread start: {e}")
            self.User = False # Assume user check failed if setup fails
            # Ensure self.ln and self.cln are available for msgError, even if translations failed.
            error_msg_key = "user_check_thread_err"
            default_err_msg = "Could not initialize user status check. Some features might be limited."
            msg_to_show = self.ln.get(error_msg_key, {}).get(self.cln, default_err_msg)
            self.msgError(msg_to_show)


    def checkVer(self, value):
        try:
            if value and isinstance(value, (list, tuple)) and len(value) >= 1:
                if value[0] != "last version":
                    ver = value[0]
                    link = value[1] if len(value) > 1 else "#" # Default link if missing
                    # Ensure self.ln and self.cln are available for msgError
                    update_msg1_key = "update_available_msg1"
                    update_msg2_key = "update_available_msg2"
                    download_lbl_key = "download_lbl"

                    default_msg1 = f"New version ({ver}) is available."
                    default_msg2 = "Please download and install it."
                    default_download = "Download"

                    msg1 = self.ln.get(update_msg1_key, {}).get(self.cln, default_msg1)
                    msg2 = self.ln.get(update_msg2_key, {}).get(self.cln, default_msg2)
                    download_text = self.ln.get(download_lbl_key, {}).get(self.cln, default_download)

                    self.msgError(
                        fr"""<html><head/><body><p align="center">{msg1}</p><p align="center">{msg2} <a href="{
                            link}"><span style=" text-decoration: underline; color:#0000ff;">{download_text}</span></a></p></body></html>""",
                        colorf="#034a0d")
                else:
                    log.info("Application is up to date.")
            else:
                log.warning(f"Received malformed version data: {value}")
        except Exception as e:
            log.exception(f"Error processing version check data: {value}. Error: {e}")


    def maxmin(self):
        if self.ui.btn_maxmin.text() == '类':
            self.MainWindow.showMaximized()
            self.ui.btn_maxmin.setText('缾')
        elif self.ui.btn_maxmin.text() == '缾':
            self.MainWindow.setWindowState(Qt.WindowNoState)
            self.ui.btn_maxmin.setText('类')

    def showNumberList(self, commandSQL, focus=0):
        # This method assumes 'db' (QSqlDatabase instance) is managed (opened/closed) externally,
        # or it needs to handle open/close itself carefully if it's the sole user for this operation.
        # For now, let's assume db should be open before calling this.
        opened_by_this_method = False
        try:
            global db # Assuming db is the global QSqlDatabase instance
            if not db.isOpen():
                log.warning("showNumberList: Database was not open. Attempting to open.")
                db.setDatabaseName(self.dbPath) # Ensure correct DB path
                if not db.open():
                    log.error(f"showNumberList: Failed to open database: {db.lastError().text()}")
                    self.msgError(f"{self.ln['db_open_err'][self.cln]}: {db.lastError().text()}")
                    return
                opened_by_this_method = True

            self.projectModel = ColorfullSqlQueryModel()
            if not self.projectModel.setQuery(commandSQL, db): # Check if setQuery was successful
                error_text = self.projectModel.lastError().text()
                log.error(f"showNumberList: SQL query failed: {error_text}. Query: {commandSQL}")
                self.msgError(f"{self.ln['db_query_err'][self.cln]}: {error_text}")
                # self.projectModel.deleteLater() # Clean up if query failed
                # self.projectModel = None
                return # Don't proceed if query failed

            tel = self.ln["tb_header_tel"][self.cln]
            st = self.ln["tb_header_st"][self.cln]
            ress = self.ln["tb_header_ress"][self.cln]
            self.projectModel.setHeaderData(0, Qt.Horizontal, tel)
            self.projectModel.setHeaderData(1, Qt.Horizontal, st)
            self.projectModel.setHeaderData(2, Qt.Horizontal, ress)
            self.ui.tableview_numbers.setModel(self.projectModel)
            self.rowCount = self.projectModel.rowCount()
            # self.tableResult = projectModel
            red = []
            green = []
            for i in range(self.rowCount):
                res = self.projectModel.record(i).value("res")
                if res == '☑':
                    green.append(i)
                elif res == '☒':
                    red.append(i)
            self.projectModel.setRowsToBeColored(red=red, green=green)
            if focus != 0:
                self.index = self.projectModel.index(focus, 2)
                if (self.index.isValid()):
                    self.ui.tableview_numbers.scrollTo(self.index)
                    self.ui.tableview_numbers.selectRow(focus)
                    log.debug("scroll")
            # QApplication.processEvents()
        except Exception as e:
            if hasattr(e, 'message'):
                log.exception(fr"{e.message}")
                errormsg = e.message
            else:
                log.debug(e)
                errormsg = e
            self.msgError(f"{self.ln['showlist_unknown_err'][self.cln]}: {errormsg}")
        finally:
            if opened_by_this_method and db.isOpen():
                db.close()
                log.debug("showNumberList: Closed database connection opened by this method.")


    def Time(self):
        tz = timezone('Asia/Tehran')
        timeZ = dt.now(tz)
        # last_time = int(time.time())   ## now timestamp
        timeZ = timeZ.strftime("%Y%m%d%H%M%S")
        return timeZ

    def ListLoader(self, path):
        self.ui.btn_export.setEnabled(False)
        if path:
            NUMBERS = []
            type = path.split('.')[-1]
            if type == 'csv':
                with open(path, 'r+') as csvF:
                    numbers = csv.reader(csvF)
                    for number in numbers:
                        for num in number:
                            try:
                                self.areaCode = int(self.ui.areaCode.text())
                            except:
                                pass
                            try:
                                n = int(num)
                                if len(str(num)) >= 9:
                                    s98 = re.compile(fr"^{self.areaCode}", re.I)
                                    s0 = re.compile('^0', re.I)
                                    if s98.search(num):
                                        pass
                                    elif s0.search(num):
                                        num = re.sub('^0', fr"{self.areaCode}", num)
                                    else:
                                        num = fr"{self.areaCode}{num}"
                                    n = int(num)
                                    NUMBERS.append(n)
                            except:
                                continue
            elif type == 'xlsx' or type == 'xls':
                try:
                    xlrd.xlsx.ensure_elementtree_imported(False, None)
                    xlrd.xlsx.Element_has_iter = True
                except:
                    pass
                wb = xlrd.open_workbook(path)
                sheet = wb.sheet_by_index(0)
                for c in range(sheet.ncols):
                    for r in range(sheet.nrows):
                        nume = sheet.cell_value(r, c)
                        try:
                            self.areaCode = int(self.ui.areaCode.text())
                        except:
                            pass
                        try:
                            num = str(int(nume))
                            if len(str(num)) >= 9:
                                s98 = re.compile(fr"^{self.areaCode}", re.I)
                                s0 = re.compile('^0', re.I)
                                if s98.search(num):
                                    pass
                                elif s0.search(num):
                                    num = re.sub('^0', fr"{self.areaCode}", num)
                                else:
                                    num = fr"{self.areaCode}{num}"
                                n = int(num)
                                NUMBERS.append(n)
                        except:
                            continue
            NUMBERS = set(NUMBERS) # Remove duplicates
            if not NUMBERS:
                log.info("ListLoader: No valid numbers found in the file to load.")
                self.msgError(self.ln["listloader_nonum_err"][self.cln], icon='Information')
                self.ui.btn_export.setEnabled(True) # Re-enable export as operation finished (no data)
                return

            self.ui.lcdNumber_allCount.display(len(NUMBERS))

            global db # The QSqlDatabase instance
            global TableNow # Name of the current table

            # Critical section: If QSqlDatabase `db` is open and using self.dbPath, it MUST be closed before os.remove or sqlite3.connect
            if db.isOpen():
                if db.databaseName() == self.dbPath:
                    log.info(f"ListLoader: Global QSqlDatabase 'db' is open with {self.dbPath}. Closing it before overwrite.")
                    db.close()
                else:
                    # This case should ideally not happen if dbPath is consistent.
                    log.warning(f"ListLoader: Global QSqlDatabase 'db' is open but with a different file ({db.databaseName()}). Proceeding with caution for {self.dbPath}.")

            # Attempt to remove the old database file if it exists
            if os.path.exists(self.dbPath):
                try:
                    os.remove(self.dbPath)
                    log.info(f"ListLoader: Removed existing database file: {self.dbPath}")
                except OSError as e:
                    log.error(f"ListLoader: Could not remove existing database file {self.dbPath}: {e}")
                    self.msgError(f"{self.ln['db_remove_err'][self.cln]}: {e}")
                    self.ui.btn_export.setEnabled(True)
                    return

            # Connect using sqlite3 for initial table creation and bulk insert
            # This is kept from original logic, assuming it's for performance or specific sqlite3 features.
            conn = None
            try:
                conn = sqlite3.connect(self.dbPath)
                cursor = conn.cursor()
                log.info(f"ListLoader: Connected to new SQLite database: {self.dbPath} using sqlite3 module.")
                TableNow = self.Time() # Generate new table name
                table_sql = fr"CREATE TABLE IF NOT EXISTS `{TableNow}` (num INT PRIMARY KEY NOT NULL, status VARCHAR(50), res VARCHAR(12))"
                cursor.execute(table_sql)
                log.info(f"ListLoader: Table `{TableNow}` created successfully.")

                # Batch insert for potentially better performance
                insert_sql = fr"INSERT INTO `{TableNow}` (num, status) VALUES (?, ?)"
                numbers_to_insert = [(int(num), '') for num in NUMBERS] # Ensure num is int
                cursor.executemany(insert_sql, numbers_to_insert)
                conn.commit()
                log.info(f"ListLoader: Inserted {len(NUMBERS)} numbers into `{TableNow}`.")

                self.ui.LogBox.clear()
                self.ui.LogBox.appendPlainText(self.ln["listloader_sucs_msg"][self.cln])

                # Now, set up the global QSqlDatabase 'db' to use this new file and table
                db.setDatabaseName(self.dbPath)
                if not db.open():
                    log.error(f"ListLoader: Failed to re-open QSqlDatabase for {self.dbPath}: {db.lastError().text()}")
                    self.msgError(f"{self.ln['db_reopen_err'][self.cln]}: {db.lastError().text()}")
                    return # Cannot show list if DB doesn't open

                self.showNumberList(commandSQL=fr"SELECT * FROM `{TableNow}`")
                self.ui.btn_clear.setEnabled(True)

            except sqlite3.Error as e:
                log.exception(f"ListLoader: sqlite3 error during database operation: {e}")
                self.msgError(f"{self.ln['db_sqlite_err'][self.cln]}: {e}")
            except Exception as e: # Catch other potential errors
                log.exception(f"ListLoader: Unexpected error: {e}")
                self.msgError(f"{self.ln['listloader_unknown_err'][self.cln]}: {e}")
            finally:
                if conn:
                    conn.close()
                    log.info("ListLoader: Closed sqlite3 connection.")
                # Ensure global QSqlDatabase is open for subsequent operations if ListLoader was successful
                if not db.isOpen() and TableNow: # If table was created, try to ensure db is open
                    log.info("ListLoader: Attempting to ensure global QSqlDatabase is open post-load.")
                    db.setDatabaseName(self.dbPath)
                    if not db.open():
                         log.error(f"ListLoader: Critical - Failed to keep global QSqlDatabase open: {db.lastError().text()}")
                         self.msgError(self.ln['db_ zůstate_err'][self.cln]) # A new lang key for this specific error
                self.ui.btn_export.setEnabled(True) # Re-enable export button

        elif type == 'xlsx' or type == 'xls':
            try:
                xlrd.xlsx.ensure_elementtree_imported(False, None)
                xlrd.xlsx.Element_has_iter = True
            except AttributeError: # Handle cases where these attributes might not exist in newer/minimal xlrd
                pass
            try:
                wb = xlrd.open_workbook(path)
                sheet = wb.sheet_by_index(0)
            except xlrd.XLRDError as e:
                log.error(f"ListLoader: XLRDError opening Excel file {path}: {e}")
                self.msgError(f"{self.ln['xlrd_err'][self.cln]}: {e}")
                self.ui.btn_export.setEnabled(True)
                return
            except FileNotFoundError:
                log.error(f"ListLoader: Excel file not found: {path}")
                self.msgError(f"{self.ln['file_not_found_err'][self.cln]}: {path.split('/')[-1]}")
                self.ui.btn_export.setEnabled(True)
                return
            except OSError as e:
                log.error(f"ListLoader: OSError reading Excel file {path}: {e}")
                self.msgError(f"{self.ln['os_err_read'][self.cln]}: {e}")
                self.ui.btn_export.setEnabled(True)
                return

            for c in range(sheet.ncols):
                for r in range(sheet.nrows):
                    nume = sheet.cell_value(r, c)
                    try:
                        self.areaCode = int(self.ui.areaCode.text())
                    except ValueError: # If area code is not a valid int, use a default or skip area code logic
                        log.warning("ListLoader: Invalid area code, using default or no prefix.")
                        self.areaCode = "" # Or some default like "98"
                        # self.ui.areaCode.setText(str(self.areaCode)) # Optionally update UI

                    try:
                        num_str = str(nume)
                        if '.' in num_str: # Handle floats that xlrd might return (e.g., 123.0)
                            num_str = num_str.split('.')[0]

                        if len(num_str) >= 9 and num_str.isdigit(): # Basic validation
                            s_prefix = re.compile(fr"^{self.areaCode}", re.I) if self.areaCode else None
                            s_zero = re.compile('^0', re.I)

                            if self.areaCode and s_prefix and s_prefix.search(num_str):
                                pass # Already has area code
                            elif s_zero.search(num_str):
                                num_str = re.sub('^0', str(self.areaCode) if self.areaCode else '', num_str)
                            elif self.areaCode : # Add area code if it doesn't start with 0 and areaCode is set
                                num_str = str(self.areaCode) + num_str

                            if num_str.isdigit(): # Final check after manipulation
                                NUMBERS.append(int(num_str))
                    except ValueError: # If num_str cannot be converted to int or other issues
                        log.debug(f"ListLoader: Skipping invalid number entry from Excel: {nume}")
                        continue
            # After processing Excel, call the part of the function that handles DB ops
            # This recursive call is a bit complex; refactoring might be better, but for now:
            # Create a temporary CSV from these numbers to reuse the CSV logic for DB insertion
            if NUMBERS:
                temp_csv_path = os.path.join("temp", f"from_excel_{self.Time()}.csv")
                try:
                    with open(temp_csv_path, 'w', newline='') as temp_f:
                        writer = csv.writer(temp_f)
                        for num_val in NUMBERS: # NUMBERS now contains integers
                            writer.writerow([num_val])
                    self.ListLoader(temp_csv_path) # Call self with the new CSV
                except (OSError, IOError) as e:
                    log.error(f"ListLoader: Error writing temporary CSV for Excel import: {e}")
                    self.msgError(f"{self.ln['temp_csv_err'][self.cln]}: {e}")
                    self.ui.btn_export.setEnabled(True)
                finally:
                    if os.path.exists(temp_csv_path):
                        try:
                            os.remove(temp_csv_path)
                        except OSError as e:
                            log.warning(f"ListLoader: Could not remove temporary CSV {temp_csv_path}: {e}")
            else: # No valid numbers from Excel
                log.info("ListLoader: No valid numbers found in the Excel file to load.")
                self.msgError(self.ln["listloader_nonum_err"][self.cln], icon='Information')
                self.ui.btn_export.setEnabled(True)

        else: # Path provided but not csv, xlsx, or xls
            log.warning(f"ListLoader: Unsupported file type: {type} for path: {path}")
            self.msgError(f"{self.ln['file_type_err'][self.cln]}: {type}", icon='Warning')
            self.ui.btn_export.setEnabled(True) # Re-enable export as operation finished
            return # Explicit return if no path or unsupported type
        # Fallthrough for the initial `if path:` condition being false
        if not path:
            log.debug("ListLoader: No file path provided.")
            # self.msgError("No file selected.", icon='Information') # Or just do nothing
            self.ui.btn_export.setEnabled(True) # Ensure export is enabled if no file was processed


    def msgError(self, errorText='مشکلی پیش آمده است !!!', icon='', colorf="#ff0000"):
        box = QMessageBox()
        if icon == '':
            box.setIcon(QMessageBox.Warning)
        else:
            box.setIcon(QMessageBox.Information)
        box.setWindowTitle('ارور')
        icon = QIcon()
        icon.addPixmap(QPixmap(":/main/icon.ico"), QIcon.Normal, QIcon.Off)
        box.setWindowIcon(icon)
        box.setText(errorText)
        box.setStandardButtons(QMessageBox.Yes)
        buttonY = box.button(QMessageBox.Yes)
        buttonY.setText(self.ln["msgerr_ok"][self.cln])
        box.setStyleSheet("""QMessageBox{\n
                          background-color:    #d9c9a3    ;\n
                          border: 3px solid   #ff0000  ;\n
                          border-radius:5px;\n
                          }\n
                          QLabel{\n
                          color:   %s  ;\n
                          font: 12pt \"Arial\";\n
                          font-weight: bold;\n
                          border:no;\n
                          }\n
                          \n
                          QPushButton:hover:!pressed\n
                          {\n
                            border: 2px dashed rgb(255, 85, 255);\n
                              background-color:  #e4e7bb ;\n
                              color:  #9804ff ;\n
                          }\n
                          QPushButton{\n
                          background-color:  #a2fdc1 ;\n
                          font: 12pt \"Arial\";\n
                          font-weight: bold;\n
                              color:  #ff0000 ;\n
                          border: 2px solid  #8b00ff ;\n
                          border-radius: 8px;\n
                          }""" % colorf)
        box.setWindowFlags(box.windowFlags() | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        box.exec_()

    def lcdNumber_reviewed(self, counter):
        self.reviewedCount = counter
        if not self.stopProgress:
            self.ui.lcdNumber_reviewed.display(counter)

    def lcdNumber_wa(self, value):
        if not self.stopProgress:
            self.ui.lcdNumber_wa.display(value)

    def lcdNumber_nwa(self, value):
        if not self.stopProgress:
            self.ui.lcdNumber_nwa.display(value)

    def programLog(self, log):
        if not self.stopProgress:
            self.ui.LogBox.appendPlainText(log)
            self.ui.LogBox.moveCursor(QTextCursor.End)

    def waINS(self, number):
        log.debug(f"waINS called for number: {number}")
        global db, TableNow
        if not db.isOpen():
            log.warning("waINS: Database is not open. Attempting to open.")
            db.setDatabaseName(self.dbPath) # Ensure correct DB
            if not db.open():
                log.error(f"waINS: Failed to open database: {db.lastError().text()}")
                # self.msgError(f"Database error in waINS: {db.lastError().text()}") # Avoid flooding user
                return

        query = QSqlQuery()
        current_tab_index = self.ui.start_tab.currentIndex()
        status_val = ""
        if current_tab_index == 0: status_val = '✓'    # Analyzed
        elif current_tab_index == 1: status_val = '✓✓'   # Message Sent
        elif current_tab_index == 2: status_val = '✓✓✓'  # Image Sent

        sql_command = fr"UPDATE `{TableNow}` SET status = '{status_val}', res = '☑' WHERE num = '{number}'"

        if not query.exec_(sql_command):
            error_text = query.lastError().text()
            log.error(f"waINS: SQL query failed for number {number}: {error_text}. Command: {sql_command}")
            # self.msgError(f"DB Update Error (waINS): {error_text}") # Avoid flooding
        else:
            log.info(f"waINS: Successfully updated number {number} with status '{status_val}' and res '☑'")
            self.showNumberList(commandSQL=fr"SELECT * FROM `{TableNow}`", focus=self.reviewedCount)
        # db.close() # Assuming db is managed globally, do not close here unless opened by this method. # Corrected in previous step

    def nwaINS(self, number):
        log.debug(f"nwaINS called for number: {number}")
        global db, TableNow
        if not TableNow: # Check if TableNow is set
            log.error("nwaINS: TableNow is not defined. Cannot update database.")
            return
        if not db.isOpen():
            log.warning("nwaINS: Database is not open. Attempting to open.")
            db.setDatabaseName(self.dbPath)
            if not db.open():
                log.error(f"nwaINS: Failed to open database: {db.lastError().text()}")
                # self.msgError(f"Database error in nwaINS: {db.lastError().text()}")
                return

        query = QSqlQuery()
        current_tab_index = self.ui.start_tab.currentIndex()
        status_val = ""
        if current_tab_index == 0: status_val = '✓'
        elif current_tab_index == 1: status_val = '✓✓'
        elif current_tab_index == 2: status_val = '✓✓✓'

        sql_command = fr"UPDATE `{TableNow}` SET status = '{status_val}', res = '☒' WHERE num = '{number}'"

        if not query.exec_(sql_command):
            error_text = query.lastError().text()
            log.error(f"nwaINS: SQL query failed for number {number}: {error_text}. Command: {sql_command}")
            # self.msgError(f"DB Update Error (nwaINS): {error_text}")
        else:
            log.info(f"nwaINS: Successfully updated number {number} with status '{status_val}' and res '☒'")
            self.showNumberList(commandSQL=fr"SELECT * FROM `{TableNow}`", focus=self.reviewedCount)
        # db.close() # Assuming db is managed globally. # Corrected

    def EndWork(self, msg=''):
        log.info(f"EndWork called with message: '{msg}' and stopProgress: {self.stopProgress}")
        if not self.stopProgress:
            self.ui.btn_start.setEnabled(True)
            self.ui.btn_stop.setEnabled(False)
            self.ui.btn_import.setEnabled(True)
            self.ui.btn_gnarate.setEnabled(True)
            self.ui.start_tab.setEnabled(True)
            self.ui.btn_export.setEnabled(True)
            self.ui.btn_clear.setEnabled(True)

            if msg: # Only process message if it's not empty
                try:
                    self.ui.LogBox.appendPlainText(msg)
                    # Check for error keywords
                    error_keywords = ["failed", "error", "timeout", "invalid", "critical"] # Add more if needed
                    if any(keyword in msg.lower() for keyword in error_keywords):
                        # Avoid showing generic "مشکلی پیش آمده است !!!" if msg already explains the error
                        detailed_error_msg = msg if msg else self.ln["msgerr_default"][self.cln]
                        self.msgError(f"{self.ln['op_report_lbl'][self.cln]}: {detailed_error_msg}", icon='Warning')
                except Exception as e:
                    log.exception(f"Error processing message in EndWork: {e}")
                    # Fallback error message if processing 'msg' itself fails
                    self.msgError(self.ln["endwork_proc_err"][self.cln])
        else: # stopProgress is True
            log.info("EndWork: stopProgress is True, UI elements not re-enabled.")
            # Optionally, you might want to log the message here too if it's relevant even when stopping
            if msg:
                self.ui.LogBox.appendPlainText(f"Stopped - Original EndWork message: {msg}")


    def stop_progress(self):
        log.debug("stop_progress called")
        # self.EndWork() # Calling EndWork here might be problematic if stopProgress is set first.
        # EndWork's logic depends on stopProgress.
        # It's better to set stopProgress and then let the running thread call EndWork.
        # Or, if stop_progress is meant to be an immediate UI update and thread stop:

        self.stopProgress = True # Set the flag first

        # Update UI immediately to reflect stop state
        self.ui.btn_start.setEnabled(True) # Allow starting a new task
        self.ui.btn_stop.setEnabled(False) # Disable stop button as it's already stopping
        self.ui.btn_import.setEnabled(True)
        self.ui.btn_gnarate.setEnabled(True)
        self.ui.start_tab.setEnabled(True)
        self.ui.btn_export.setEnabled(True)
        self.ui.btn_clear.setEnabled(True)

        entText = f"-- {self.ln['stop_prog_msg'][self.cln]} --"
        self.ui.LogBox.appendPlainText(entText)
        log.info(entText)

        try:
            # Determine which thread is active based on self.ThreadName or current tab
            # Assuming self.ThreadName holds the currently active thread instance
            if hasattr(self, 'ThreadName') and self.ThreadName and self.ThreadName.isRunning():
                log.info(f"Stopping thread: {self.ThreadName}")
                self.ThreadName.stop()
            # Fallback or alternative if self.ThreadName isn't reliably set for all threads
            elif hasattr(self, 'AnalyzThread') and self.AnalyzThread.isRunning():
                 log.info("Stopping AnalyzThread")
                 self.AnalyzThread.stop()
            elif hasattr(self, 'MsgThread') and self.MsgThread.isRunning():
                 log.info("Stopping MsgThread")
                 self.MsgThread.stop()
            elif hasattr(self, 'ImgThread') and self.ImgThread.isRunning():
                 log.info("Stopping ImgThread")
                 self.ImgThread.stop()
            else:
                log.info("stop_progress: No active thread found to stop or ThreadName not set.")
        except Exception as e:
            log.exception(f"Error stopping thread in stop_progress: {e}")
            self.msgError(f"{self.ln['thread_stop_err'][self.cln]}: {e}")

    def AnalyzNum(self):
        try:
            if db.open():
                # QApplication.processEvents()
                log.debug("Analyz OK")
                query = QSqlQuery()
                query.exec_(fr"select * from `{TableNow}` where status = ''")
                numList = []
                while query.next():
                    num = query.value(0)
                    numList.append(num)
                self.AnalyzThread = Web(counter_start=0, step='A', numList=numList, Remember=self.RememberLogin)
                self.AnalyzThread.start()
                log.debug("send start command for browser")
                self.AnalyzThread.lcdNumber_reviewed.connect(self.lcdNumber_reviewed)
                self.AnalyzThread.lcdNumber_wa.connect(self.lcdNumber_wa)
                self.AnalyzThread.lcdNumber_nwa.connect(self.lcdNumber_nwa)
                self.AnalyzThread.LogBox.connect(self.programLog)
                self.AnalyzThread.wa.connect(self.waINS)
                self.AnalyzThread.nwa.connect(self.nwaINS)
                self.AnalyzThread.EndWork.connect(self.EndWork)
                self.stopProgress = False
        except Exception as e:
            if hasattr(e, 'message'):
                log.exception(e.message)
            else:
                log.debug(e)
            self.msgError(self.ln["analyz_err"][self.cln]) # General error for AnalyzNum setup
            # Ensure UI is reset if setup fails
            self.EndWork(f"-- {self.ln['analyz_op_lbl'][self.cln]} {self.ln['setup_fail_lbl'][self.cln]} --")


    def sendMsg(self, text):
        log.debug("sendMsg: Initializing message sending.")
        global db, TableNow
        opened_by_this_method = False
        try:
            if not TableNow:
                log.error("sendMsg: TableNow is not defined. Cannot proceed.")
                self.msgError(self.ln["db_notable_err"][self.cln])
                return

            if not db.isOpen():
                log.warning("sendMsg: Database is not open. Attempting to open.")
                db.setDatabaseName(self.dbPath)
                if not db.open():
                    log.error(f"sendMsg: Failed to open database: {db.lastError().text()}")
                    self.msgError(f"{self.ln['db_open_err'][self.cln]}: {db.lastError().text()}")
                    return
                opened_by_this_method = True

            query = QSqlQuery()
            # Select numbers that are either new or previously successful for retrying/multi-send.
            sql_select_numbers = fr"SELECT num FROM `{TableNow}` WHERE status = '' OR res = '☑'"
            if not query.exec_(sql_select_numbers):
                log.error(f"sendMsg: Failed to query numbers: {query.lastError().text()}")
                self.msgError(f"{self.ln['db_query_err'][self.cln]}: {query.lastError().text()}")
                if opened_by_this_method: db.close()
                return

            numList = []
            while query.next():
                num = query.value(0)
                numList.append(num)

            if not numList:
                log.info("sendMsg: No numbers to process.")
                self.msgError(self.ln["sendmsg_nonum_info"][self.cln], icon='Information')
                if opened_by_this_method: db.close()
                self.EndWork(f"-- {self.ln['sendmsg_op_lbl'][self.cln]} {self.ln['completed_lbl'][self.cln]} (No numbers) --")
                return

                sleepMin = self.ui.sleepMin.text()
                sleepMax = self.ui.sleepMax.text()
                if sleepMin != '':
                    sleepMin = int(sleepMin)
                else:
                    sleepMin = 3
                if sleepMax != '':
                    sleepMax = int(sleepMax)
                else:
                    sleepMax = 6
                self.MsgThread = Web(counter_start=0, step='M', numList=numList, sleepMin=sleepMin, sleepMax=sleepMax,
                                     text=text, Remember=self.RememberLogin)
                self.MsgThread.start()
                self.MsgThread.lcdNumber_reviewed.connect(self.lcdNumber_reviewed)
                self.MsgThread.lcdNumber_wa.connect(self.lcdNumber_wa)
                self.MsgThread.lcdNumber_nwa.connect(self.lcdNumber_nwa)
                self.MsgThread.LogBox.connect(self.programLog)
                self.MsgThread.wa.connect(self.waINS)
                self.MsgThread.nwa.connect(self.nwaINS)
                self.MsgThread.EndWork.connect(self.EndWork)
                self.stopProgress = False
        except Exception as e:
            if hasattr(e, 'message'):
                log.exception(e.message)
            else:
                log.debug(e)
            self.msgError(self.ln["msg_err"][self.cln]) # General error for sendMsg setup
            if opened_by_this_method and db.isOpen():
                db.close()
            self.EndWork(f"-- {self.ln['sendmsg_op_lbl'][self.cln]} {self.ln['setup_fail_lbl'][self.cln]} --")


    def sendImg(self, path, caption=''):
        log.debug("sendImg: Initializing image sending.")
        global db, TableNow
        opened_by_this_method = False
        try:
            if not TableNow:
                log.error("sendImg: TableNow is not defined. Cannot proceed.")
                self.msgError(self.ln["db_notable_err"][self.cln])
                return

            if not db.isOpen():
                log.warning("sendImg: Database is not open. Attempting to open.")
                db.setDatabaseName(self.dbPath)
                if not db.open():
                    log.error(f"sendImg: Failed to open database: {db.lastError().text()}")
                    self.msgError(f"{self.ln['db_open_err'][self.cln]}: {db.lastError().text()}")
                    return
                opened_by_this_method = True

            query = QSqlQuery()
            sql_select_numbers = fr"SELECT num FROM `{TableNow}` WHERE status = '' OR res = '☑'"
            if not query.exec_(sql_select_numbers):
                log.error(f"sendImg: Failed to query numbers: {query.lastError().text()}")
                self.msgError(f"{self.ln['db_query_err'][self.cln]}: {query.lastError().text()}")
                if opened_by_this_method: db.close()
                return

            numList = []
            while query.next():
                num = query.value(0)
                numList.append(num)

            if not numList:
                log.info("sendImg: No numbers to process for image sending.")
                self.msgError(self.ln["sendimg_nonum_info"][self.cln], icon='Information')
                if opened_by_this_method: db.close()
                self.EndWork(f"-- {self.ln['sendimg_op_lbl'][self.cln]} {self.ln['completed_lbl'][self.cln]} (No numbers) --")
                return
                sleepMin = self.ui.sleepMin_I.text()
                sleepMax = self.ui.sleepMax_I.text()
                if sleepMin != '':
                    sleepMin = int(sleepMin)
                else:
                    sleepMin = 3
                if sleepMax != '':
                    sleepMax = int(sleepMax)
                else:
                    sleepMax = 6
                self.ImgThread = Web(counter_start=0, step='I', numList=numList, sleepMin=sleepMin, sleepMax=sleepMax,
                                     text=caption, path=path, Remember=self.RememberLogin)
                self.ImgThread.start()
                self.ImgThread.lcdNumber_reviewed.connect(self.lcdNumber_reviewed)
                self.ImgThread.lcdNumber_wa.connect(self.lcdNumber_wa)
                self.ImgThread.lcdNumber_nwa.connect(self.lcdNumber_nwa)
                self.ImgThread.LogBox.connect(self.programLog)
                self.ImgThread.wa.connect(self.waINS)
                self.ImgThread.nwa.connect(self.nwaINS)
                self.ImgThread.EndWork.connect(self.EndWork)
                self.stopProgress = False
        except Exception as e:
            if hasattr(e, 'message'):
                log.exception(e.message)
            else:
                log.debug(e)
            self.msgError(self.ln["img_err"][self.cln]) # General error for sendImg setup
            if opened_by_this_method and db.isOpen():
                db.close()
            self.EndWork(f"-- {self.ln['sendimg_op_lbl'][self.cln]} {self.ln['setup_fail_lbl'][self.cln]} --")


    def btnStatus(self, status='l'):
        '''
        disable or enable btns after strat app work
        '''
        if status == 'l':
            self.ui.lcdNumber_nwa.display(0)
            self.ui.lcdNumber_wa.display(0)
            self.ui.lcdNumber_reviewed.display(0)
            self.ui.LogBox.clear()
            self.ui.btn_start.setEnabled(False)
            self.ui.btn_stop.setEnabled(True)
            self.ui.btn_import.setEnabled(False)
            self.ui.btn_clear.setEnabled(False)
            self.ui.btn_gnarate.setEnabled(False)
            self.ui.start_tab.setEnabled(False)

    def userChecker(self, value):
        # self.User = value # Original logic commented out
        self.User = True # Forcing to True as per original effective logic
        log.debug(f"userChecker: User status set to {self.User} (original value from thread: {value})")
        return self.User

    def qthreadInsert(self, value): # This seems to be a slot for a signal from NetWork thread
        log.debug(f"qthreadInsert called with value: {value}")
        if hasattr(self, 'insert') and self.insert and self.insert.isRunning():
            try:
                self.insert.stop()
                log.info("qthreadInsert: Stopped 'insert' NetWork thread.")
            except Exception as e:
                log.exception(f"qthreadInsert: Error stopping 'insert' NetWork thread: {e}")
        else:
            log.info("qthreadInsert: 'insert' NetWork thread not found or not running.")


    def StarT(self):
        try:
            self.userChck()
        except:
            pass
        self.RememberLogin = True

        log.info("Start")
        # Net = self.ConnectionCheck()
        Net = True
        try:
            log.debug(fr"{Net} {self.User}")
            global db # Ensure db is accessible
            if not db.isOpen(): # Check if DB is open, if not, try to open it.
                log.warning("StarT: Database was not open. Attempting to open.")
                db.setDatabaseName(self.dbPath) # Ensure correct DB path
                if not db.open():
                    log.error(f"StarT: Failed to open database: {db.lastError().text()}")
                    self.msgError(f"{self.ln['db_open_err'][self.cln]}: {db.lastError().text()}")
                    return # Critical error, cannot proceed without DB

            if Net: # ConnectionCheck result
                if self.User: # User license/status check
                    # Ensure TableNow is defined before proceeding with operations that need it
                    if not hasattr(self, 'TableNow') or not self.TableNow:
                        log.error("StarT: No active number list (TableNow not set). Please import or generate numbers first.")
                        self.msgError(self.ln["list_not_loaded_err"][self.cln])
                        db.close() # Close DB if opened by StarT
                        return

                    currentIndex = self.ui.start_tab.currentIndex()
                        if currentIndex == 0:
                            self.btnStatus()
                            self.ui.LogBox.appendPlainText(fr"-- Start analysis --")
                            self.AnalyzNum()
                        elif currentIndex == 1:
                            log.debug("message Tab")
                            text = self.ui.textMSG.toPlainText()
                            log.debug(text)
                            if text != '':
                                self.btnStatus()
                                self.ui.LogBox.appendPlainText(fr"-- Start Send Message --")
                                self.sendMsg(text)
                            else:
                                self.msgError(self.ln["inputxt_err"][self.cln])
                        elif currentIndex == 2:
                            log.debug('image tab')
                            if self.p != '':
                                caption = self.ui.caption.toPlainText()
                                self.ui.LogBox.appendPlainText(fr"-- Start Send Image --")
                                self.sendImg(path=self.p, caption=caption)
                                self.btnStatus()
                            else:
                                self.msgError(self.ln["inputimg_err"][self.cln])
                        else:
                            self.msgError()
                        if not self.RememberLogin:
                            lisT = os.listdir('temp')
                            import shutil
                            for f in lisT:
                                try:
                                    if f == 'temporary.data':
                                        continue
                                    os.remove(fr"temp/{f}")
                                except:
                                    try:
                                        os.rmdir(fr"temp/{f}")
                                    except:
                                        shutil.rmtree(fr"temp/{f}")
                                        continue
                                    continue
                    else:
                    self.msgError(self.ln["per_err"][self.cln], colorf='#1b6900') # Assuming User check failed
                else: # Net is False
                    self.msgError(self.ln["net_err"][self.cln]) # Network connection failed
            # Ensure db is closed if StarT opened it and an early exit occurred (e.g. Net/User check fail)
            # However, if an operation starts, it will manage the db state via its own try/finally.
            # This part is tricky with a global db. For now, let operations manage it.
            # if not (Net and self.User) and db.isOpen(): db.close()

        except Exception as e: # Catch any other unexpected errors in StarT
            log.exception(f"StarT: Unexpected error: {e}")
            self.msgError(f"{self.ln['start_unknown_err'][self.cln]}: {e}")
            if db.isOpen(): # Attempt to close DB on unexpected error
                db.close()


    def export(self):
        log.debug("export: Initiating export process.")
        global db, TableNow
        opened_by_this_method = False

        if not hasattr(self, 'TableNow') or not TableNow:
            log.warning("export: No table loaded (TableNow is not set). Nothing to export.")
            self.msgError(self.ln["export_notable_err"][self.cln], icon='Information')
            return

        try:
            if not db.isOpen():
                log.warning("export: Database is not open. Attempting to open.")
                db.setDatabaseName(self.dbPath)
                if not db.open():
                    log.error(f"export: Failed to open database: {db.lastError().text()}")
                    self.msgError(f"{self.ln['db_open_err'][self.cln]}: {db.lastError().text()}")
                    return
                opened_by_this_method = True

            DeskTop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
            appName = self.ui.label_appName.text()
            export_dir = os.path.join(DeskTop, appName)

            os.makedirs(export_dir, exist_ok=True) # exist_ok=True prevents error if dir exists

            query = QSqlQuery()
            sql_export_query = fr"SELECT num, status, res FROM `{TableNow}` WHERE res = '☑'" # Only export successful ones

            if not query.exec_(sql_export_query):
                log.error(f"export: Failed to query data for export: {query.lastError().text()}")
                self.msgError(f"{self.ln['db_query_err'][self.cln]}: {query.lastError().text()}")
                return

            exported_files = {} # To store counts per file type for summary
            has_data_to_export = False

            while query.next():
                has_data_to_export = True
                number = query.value(0)
                status = query.value(1)
                # res = query.value(2) # res is '☑' due to WHERE clause

                FileNamePrefix = "Export-"
                if status == '✓': FileNamePrefix = 'Analyzed-'
                elif status == '✓✓': FileNamePrefix = 'SentMSG-'
                elif status == '✓✓✓': FileNamePrefix = 'SentIMG-'

                # Use TableNow in filename to distinguish exports from different lists/sessions
                csv_file_name = f"{FileNamePrefix}{TableNow}.csv"
                full_csv_path = os.path.join(export_dir, csv_file_name)

                try:
                    with open(full_csv_path, 'a+', newline='', encoding='utf-8') as cSv: # Use newline='' for csv
                        writer = csv.writer(cSv, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
                        # Write header if file is new/empty
                        if cSv.tell() == 0:
                            writer.writerow(["Number"]) # Example header
                        writer.writerow([number])
                    exported_files[csv_file_name] = exported_files.get(csv_file_name, 0) + 1
                except (IOError, OSError) as e:
                    log.error(f"export: Error writing to CSV file {full_csv_path}: {e}")
                    self.msgError(f"{self.ln['export_file_write_err'][self.cln]}: {e}")
                    # Potentially stop further export for this file or continue with others

            if not has_data_to_export:
                self.msgError(self.ln["export_nodata_info"][self.cln], icon='Information')
            elif exported_files:
                summary_msg = self.ln["export_sucs_summary_lbl"][self.cln] + "\n"
                for fname, count in exported_files.items():
                    summary_msg += f"- {fname}: {count} {self.ln['records_lbl'][self.cln]}\n"
                summary_msg += f"{self.ln['location_lbl'][self.cln]}: {export_dir}"
                self.msgError(errorText=summary_msg, icon='Information', colorf="#214917")
            else: # Should not happen if has_data_to_export is true but exported_files is empty
                self.msgError(self.ln["export_unknown_info"][self.cln], icon='Information')

        except KeyError: # For os.environ['USERPROFILE']
             log.error("export: Could not get user's Desktop path (USERPROFILE environment variable missing).")
             self.msgError(self.ln["export_desktop_path_err"][self.cln])
        except OSError as e: # For os.makedirs
            log.error(f"export: Error creating export directory {export_dir}: {e}")
            self.msgError(f"{self.ln['export_dir_create_err'][self.cln]}: {e}")
        except Exception as e:
            log.exception(f"export: Unexpected error during export: {e}")
            self.msgError(f"{self.ln['export_err'][self.cln]}: {e}")
        finally:
            if opened_by_this_method and db.isOpen():
                db.close()
                log.debug("export: Closed database connection opened by this method.")


    def initGenerate(self):
        log.debug("init Generate")
        from generate import Ui_Form
        self.frOM = Ui_Form()
        self.generateForm = QDialog()
        self.generateForm.setModal(True)
        self.generateForm.setWindowFlags(self.generateForm.windowFlags() | Qt.FramelessWindowHint)
        self.generateForm.setAttribute(Qt.WA_TranslucentBackground)
        icon = QIcon()
        icon.addPixmap(QPixmap(":/main/icon.ico"), QIcon.Normal, QIcon.Off)
        self.generateForm.setWindowIcon(icon)
        self.frOM.setupUi(self.generateForm)
        self.frOM.generate_num.setValidator(self.validator)
        self.frOM.generate_num.setMaxLength(10)
        self.frOM.generate_count.setValidator(self.validator)
        self.frOM.generate_count.setMaxLength(5)
        self.frOM.btn_g_ok.setFocus()
        self.frOM.btn_g_cancel.clicked.connect(self.generateForm.close)
        self.frOM.btn_g_ok.clicked.connect(self.importGenerate)

    def generate(self):
        log.debug("btn generate")
        self.languageSet()
        self.generateForm.show()

    def importGenerate(self):
        firstNumber = self.frOM.generate_num.text()
        RangeNum = self.frOM.generate_count.text()
        if RangeNum == '':
            RangeNum = 10
        if firstNumber != '':
            if not len(firstNumber) < 9:
                path = fr"temp\generate-{self.Time()}.csv"
                log.debug(f"importGenerate: Generating numbers starting from {firstNumber}, count {RangeNum} to path {path}")
                try:
                    for i in range(int(RangeNum)):
                        # Ensure writing to CSV is robust
                        with open(path, 'a+', newline='', encoding='utf-8') as g: # Use newline=''
                            writer = csv.writer(g, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
                            writer.writerow([firstNumber])
                        firstNumber = str(int(firstNumber) + 1) # Ensure firstNumber remains string for next iteration if leading zeros matter

                    self.generateForm.close()
                    self.ListLoader(path) # ListLoader will handle its own errors
                    # Success message from ListLoader is usually sufficient. If specific message needed here:
                    # self.msgError(errorText=self.ln["listcreate_sucs"][self.cln], icon='Information', colorf="#214917")
                except (IOError, OSError) as e:
                    log.error(f"importGenerate: Error writing to temporary CSV file {path}: {e}")
                    self.msgError(f"{self.ln['temp_csv_err'][self.cln]}: {e}")
                except ValueError: # If int(RangeNum) or int(firstNumber) fails
                    log.error(f"importGenerate: Invalid number format for start number or range: {firstNumber}, {RangeNum}")
                    self.msgError(self.ln["generate_num_format_err"][self.cln])
                finally:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                            log.debug(f"importGenerate: Removed temporary file {path}")
                        except OSError as e:
                            log.warning(f"importGenerate: Could not remove temporary file {path}: {e}")
            else: # firstNumber length invalid
                self.msgError(self.ln["num_valid"][self.cln]) # Number length validation
        else:
            self.msgError(self.ln["generate_err"][self.cln])

    def initImport(self):
        try:
            if self.cv == 0: # cv is a counter, presumably to run this once
                self.cv = 1
                log.debug("Setting up application version check thread.")
                self.checkVERSION = NetWork(step=1, version=self.__VERSION__)
                self.checkVERSION.start()
                self.checkVERSION.cuurentVersion.connect(self.checkVer) # checkVer is now error-handled
        except Exception as e:
            log.exception(f"Error starting version check thread in initImport: {e}")
            # Potentially inform user or proceed without version check if non-critical

        from importNumber import Ui_Form # Keep UI setup outside try-except if it's standard Qt setup
        self.fi = Ui_Form()
        self.formQImport1 = QDialog()
        self.formQImport1.setModal(True)
        self.formQImport1.setWindowFlags(self.formQImport1.windowFlags() | Qt.FramelessWindowHint)
        self.formQImport1.setAttribute(Qt.WA_TranslucentBackground)
        self.fi.setupUi(self.formQImport1)
        icon = QIcon()
        icon.addPixmap(QPixmap(":/main/icon.ico"), QIcon.Normal, QIcon.Off)
        self.formQImport1.setWindowIcon(icon)
        self.fi.btn_import_cancel.clicked.connect(self.formQImport1.close)
        self.fi.btn_importFile.clicked.connect(self.btn_import)
        self.fi.btn_importManual.clicked.connect(self.importManual)

    def importer(self):
        self.languageSet()
        self.formQImport1.show()

    def btn_import(self):
        options = QFileDialog.Options()
        UserDesk = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
        num_path, _ = QFileDialog.getOpenFileName(caption="", directory=UserDesk,
                                                  filter="Excel Files (*.xlsx | *.xls | *.csv)", options=options)
        try:
            if num_path:
                self.formQImport1.close()
        except:
            pass
        self.ListLoader(num_path)

    def importManual(self):
        nums = self.fi.manualNumber.toPlainText()
        if nums != '':
            try:
                numLine = nums.split('\n')
                numLine = set(numLine)
                log.debug(f"importManual: Processing manually entered numbers. Count: {len(numLine)}")
                path = os.path.join("temp", f"manualNumber-{self.Time()}.csv") # Use os.path.join
                try:
                    with open(path, 'w', newline='', encoding='utf-8') as g: # Use 'w' to create new, newline=''
                        writer = csv.writer(g, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
                        valid_nums_written = 0
                        for num_str in numLine:
                            num_str = num_str.strip() # Remove whitespace
                            if not num_str: continue # Skip empty lines
                            try:
                                # Basic validation, ListLoader will do more thorough validation
                                int(num_str) # Check if it can be an int
                                writer.writerow([num_str])
                                valid_nums_written +=1
                            except ValueError:
                                log.warning(f"importManual: Skipping invalid number entry: '{num_str}'")

                    if valid_nums_written > 0:
                        self.formQImport1.close()
                        self.ListLoader(path) # ListLoader will handle its own errors
                        # Success message from ListLoader is usually sufficient
                        # self.msgError(errorText=self.ln["load_sucs"][self.cln], icon='Information', colorf="#214917")
                    else:
                        self.msgError(self.ln["manual_nonum_err"][self.cln], icon='Information')

                except (IOError, OSError) as e:
                    log.error(f"importManual: Error writing to temporary CSV file {path}: {e}")
                    self.msgError(f"{self.ln['temp_csv_err'][self.cln]}: {e}")
                except ValueError: # Should be caught by inner try now.
                     log.error(f"importManual: Invalid data found in manual input.") # Should not happen if inner try works
                     self.msgError(self.ln["num_load_err"][self.cln])
                finally:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                            log.debug(f"importManual: Removed temporary file {path}")
                        except OSError as e:
                            log.warning(f"importManual: Could not remove temporary file {path}: {e}")
            except Exception as e: # Catch any other unexpected errors from splitting/processing nums
                log.exception(f"importManual: Error processing pasted numbers: {e}")
                self.msgError(self.ln["num_load_err"][self.cln])
        else:
            self.msgError(self.ln["slctnums_err"][self.cln])

    def initAccountList(self):
        from accuonts import Ui_Form
        self.fia = Ui_Form()
        self.formQImport = QDialog()
        self.formQImport.setModal(True)
        self.formQImport.setWindowFlags(self.formQImport.windowFlags() | Qt.FramelessWindowHint)
        self.formQImport.setAttribute(Qt.WA_TranslucentBackground)
        self.fia.setupUi(self.formQImport)
        icon = QIcon() # Assuming icons_rc is correctly imported and resources are available
        icon.addPixmap(QPixmap(":/main/icon.ico"), QIcon.Normal, QIcon.Off) # Assuming icons_rc is fine
        self.formQImport.setWindowIcon(icon)
        self.fia.btn_import_cancel.clicked.connect(self.formQImport.close)

        cache_dir = os.path.join('temp', 'cache')
        try:
            os.makedirs(cache_dir, exist_ok=True)
            log.debug(f"Ensured cache directory exists: {cache_dir}")
            cacheList = os.listdir(cache_dir) # This might fail if cache_dir is not readable
            log.debug(f"Cache list: {cacheList}")
        except OSError as e:
            log.error(f"Failed to create or list cache directory {cache_dir}: {e}")
            # Provide a default for cache_dir_err if not in self.ln
            default_cache_err_msg = "Error accessing account cache. Account features might be affected."
            err_msg_key = "cache_dir_err"
            # Safely get the error message from translations or use default
            final_err_msg = self.ln.get(err_msg_key, {}).get(self.cln, default_cache_err_msg)
            self.msgError(f"{final_err_msg}: {cache_dir}")
            cacheList = [] # Use empty list if dir cannot be accessed/created

        self.modelAcc = TableModel(cacheList)
        self.fia.accountsTable.setModel(self.modelAcc)
        # self.rowCount = self.modelAcc.rowCount()
        # self.fia.btn_importaccount.clicked.connect(self.addAccounts)
        # self.fia.btn_importaccount.setEnabled(False)
        self.fia.btn_importaccount.clicked.connect(lambda: self.msgError(
            errorText=self.ln["undefine_feature"][self.cln], icon="", colorf="#0013ff"))

    def accountsList(self):
        self.languageSet()
        self.formQImport.show()

    def addAccounts(self):
        '''
        Add new account to my account list , with get text account name from user
        '''
        newaccountName = self.fia.btn_addnewtel.text()
        if newaccountName != '':
            self.addAccount = Web(step='Add', path=newaccountName, Remember=True)
            self.addAccount.start()
        else:
            self.msgError(self.ln["acc_num"][self.cln])

    def clearList(self):
        try:
            log.debug("clearList: Attempting to clear table view and delete model.")
            if hasattr(self, 'projectModel') and self.projectModel is not None:
                self.projectModel.clear() # Clear model data
                self.ui.tableview_numbers.setModel(None) # Detach model from view
                self.projectModel.deleteLater() # Schedule for deletion
                self.projectModel = None # Set to None
                log.info("clearList: projectModel cleared and scheduled for deletion.")
            else:
                log.info("clearList: No projectModel found to clear.")
            # Optionally, reset LCDs and LogBox here if desired when clearing the list
            self.ui.lcdNumber_allCount.display(0)
            self.ui.lcdNumber_reviewed.display(0)
            self.ui.lcdNumber_wa.display(0)
            self.ui.lcdNumber_nwa.display(0)
            self.ui.LogBox.clear()
            self.ui.btn_export.setEnabled(False) # Disable export if list is cleared
            self.ui.btn_clear.setEnabled(False) # Disable clear again
        except Exception as e:
            log.exception(f"clearList: Error clearing list/model: {e}")
            self.msgError(f"{self.ln['clearlist_err'][self.cln]}: {e}")


    def selectIMG(self):
        options = QFileDialog.Options()
        UserDesk = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
        img_path, _ = QFileDialog.getOpenFileName(caption="", directory=UserDesk,
                                                  filter="Image Files (*.jpg | *.jpeg | *.png)", options=options)
        self.p = img_path
        try:
            if img_path:
                log.debug(img_path)
                imgName = img_path.split('/')[-1]
                img = QPixmap(img_path)
                if img.isNull():
                    log.error(f"selectIMG: Failed to load image from path: {img_path}. Image is null.")
                    self.msgError(f"{self.ln['img_load_err'][self.cln]}: {imgName}", icon='Warning')
                    self.ui.imgShow.clear() # Clear previous image if any
                    self.ui.imgName.clear()
                    self.p = '' # Reset path
                    return

                img1 = img.scaled(120, 120, Qt.KeepAspectRatio)
                self.ui.imgShow.setPixmap(img1)
                self.ui.imgName.setText(imgName)
            else: # img_path is empty (user cancelled dialog)
                log.debug("selectIMG: No image file selected.")
        except Exception as e: # Catch any other unexpected error during image processing
            log.exception(f"selectIMG: Unexpected error processing image {img_path}: {e}")
            self.msgError(f"{self.ln['img_proc_err'][self.cln]}: {e}", icon='Warning')
            self.ui.imgShow.clear()
            self.ui.imgName.clear()
            self.p = ''


    def ConnectionCheck(self, url='https://www.whatsapp.com/', timeout=5):
        try:
            req = requests.get(url, timeout=timeout)
            req.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)
            log.info("ConnectionCheck: Successfully connected to WhatsApp URL.")
            return True
        except requests.exceptions.HTTPError as e: # More specific requests exception
            log.warning(f"ConnectionCheck: HTTPError - Failed, status code {e.response.status_code} for {url}.")
            return False
        except requests.exceptions.ConnectionError as e: # More specific requests exception
            log.warning(f"ConnectionCheck: ConnectionError - No internet or server not reachable for {url}. Error: {e}")
            return False
        except requests.exceptions.Timeout as e: # More specific requests exception
            log.warning(f"ConnectionCheck: Timeout when trying to connect to {url}. Error: {e}")
            return False
        except requests.exceptions.RequestException as e: # Catch any other requests error
            log.warning(f"ConnectionCheck: A request exception occurred for {url}. Error: {e}")
            return False


class myQMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.oldPos = self.pos()

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()


class LoadingText(QMessageBox):
    def __init__(self, timeout=3, parent=None):
        super(LoadingText, self).__init__(parent)
        self.setWindowTitle("Loading...")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setStyleSheet('''QLabel{color:#ff0000;}''')
        self.time_to_wait = timeout
        self.setText("wait (closing automatically in {0} secondes.)".format(timeout))
        self.setStandardButtons(QMessageBox.NoButton)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.changeContent)
        self.timer.start()

    def changeContent(self):
        self.time_to_wait -= 1
        self.setText("wait (closing automatically in {0} secondes.)".format(self.time_to_wait))
        if self.time_to_wait <= 0:
            self.close()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()


class ColorfullSqlQueryModel(QSqlQueryModel):
    def __init__(self, dbcursor=None):
        super(ColorfullSqlQueryModel, self).__init__()
        self.red = []
        self.green = []

    def setRowsToBeColored(self, red=None, green=None):
        if red != None:
            self.red = red
        if green != None:
            self.green = green

    def data(self, index, role):
        row = index.row()
        if role == Qt.BackgroundRole and row in self.red:
            return QBrush(QColor('#FC500B'))
        if role == Qt.BackgroundRole and row in self.green:
            return QBrush(QColor('#AEF77E'))
        return QSqlQueryModel.data(self, index, role)


class NetWork(QThread):
    cuurentVersion = pyqtSignal(object)
    Checker = pyqtSignal(bool)

    def __init__(self, parent=None, step=0, version=None, user=None, pw=0):
        super(NetWork, self).__init__(parent)
        self.version = version
        self.step = step
        self.user = user
        self.pw = pw

    def Time(self):
        tz = timezone('Asia/Tehran')
        timeZ = dt.now(tz)
        # last_time = int(time.time())   ## now timestamp
        timeZ = timeZ.strftime("%Y%m%d%H%M%S")
        return timeZ

    def STATUS(self, user=None, pw=0):
        self.Checker.emit(True)
        return ''

    def insertMember(self, version):
        pass

    def run(self):
        if self.step == 0:
            self.insertMember(self.version)
        elif self.step == 1:
            pass
            # self.checkVersion(self.version)
        elif self.step == 2:
            self.STATUS(user=self.user, pw=self.pw)

    def stop(self):
        log.debug('terminate thread')
        self.terminate()


class TableModel(QAbstractTableModel):
    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return self._data[index.row()]

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return 1

    def headerData(self, section, orientation, role):

        if role == Qt.DisplayRole:
            return "*"

# Ensure src/logs directory exists as early as possible
try:
    os.makedirs('src/logs', exist_ok=True)
except OSError as e:
    # This might fail if permissions are an issue, print to stderr as a last resort.
    # Using print here because logging might not be set up yet.
    print(f"Critical: Could not create src/logs directory: {e}", file=sys.stderr)

def main():
    try:
        run = Main()
    except Exception as e:
        # Fallback logging if appLog or Main.__init__ fails catastrophically
        fallback_log_path = 'src/logs/main_fallback.log'
        # Basic console print for immediate visibility
        print(f"CRITICAL ERROR during Main() instantiation: {e}\nTraceback written to {fallback_log_path}", file=sys.stderr)

        # Attempt to write to fallback log
        try:
            # Configure a basic logger for the fallback
            fallback_logger = logging.getLogger('main_fallback')
            # Ensure handler is not added multiple times if this code somehow runs more than once
            if not fallback_logger.handlers:
                handler = logging.FileHandler(fallback_log_path)
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                fallback_logger.addHandler(handler)
                fallback_logger.setLevel(logging.DEBUG) # Capture all details

            fallback_logger.critical("CRITICAL ERROR during Main() instantiation:", exc_info=True)
        except Exception as log_e:
            # If even fallback logging fails, print that error to stderr
            print(f"CRITICAL: Failed to write to fallback log {fallback_log_path}: {log_e}", file=sys.stderr)
        sys.exit(1) # Exit with an error code

if __name__ == '__main__':
    main()    # from multiprocessing import Process
    # p1 = Process(target=Main)
    # srv = NetWork()
    # p2 =Process(target=srv.insertMember,args=('1.0',))
    # p1.start()
    # p2.start()
    # p1.join()
    # p2.join()
