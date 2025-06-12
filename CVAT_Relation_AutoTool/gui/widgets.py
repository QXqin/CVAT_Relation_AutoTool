import tkinter as tk
from tkinter import ttk


class ProgressFrame(ttk.LabelFrame):
    """进度显示组件"""

    def __init__(self, parent):
        super().__init__(parent, text="处理进度")

        self.progress_bar = ttk.Progressbar(
            self,
            orient=tk.HORIZONTAL,
            length=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)

        self.status_label = ttk.Label(
            self,
            text="准备就绪，请选择 CVAT XML 文件",
            padding=5
        )
        self.status_label.pack(fill=tk.X, padx=10, pady=(0, 5))

    def update(self, progress, message):
        """更新进度"""
        self.progress_bar['value'] = progress
        self.status_label.config(text=message)
        self.update_idletasks()