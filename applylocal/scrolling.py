"""A whole-window scroll surface with nested-control wheel routing."""
import tkinter as tk
from tkinter import ttk
import weakref


class ScrollableFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, yscrollincrement=24)
        self.bar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.bar.grid(row=0, column=1, sticky='ns')
        self.content = ttk.Frame(self.canvas, padding=18)
        self.window = self.canvas.create_window(0, 0, window=self.content, anchor='nw')
        self.content.bind('<Configure>', self._content_changed)
        self.canvas.bind('<Configure>', self._resized)
        root = self._root()
        if not hasattr(root, '_applylocal_scroll_surfaces'):
            root._applylocal_scroll_surfaces = weakref.WeakSet()
            for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
                root.bind_all(sequence, lambda event: ScrollableFrame._route(root, event), add='+')
        root._applylocal_scroll_surfaces.add(self)
        master.bind('<Next>', lambda e: self._page(e, 1), add='+')
        master.bind('<Prior>', lambda e: self._page(e, -1), add='+')
        master.bind('<End>', lambda e: self._edge(e, 1), add='+')
        master.bind('<Home>', lambda e: self._edge(e, 0), add='+')

    @staticmethod
    def _route(root, event):
        for surface in list(root._applylocal_scroll_surfaces):
            try:
                if surface.winfo_toplevel() == event.widget.winfo_toplevel():
                    return surface._wheel(event)
            except tk.TclError:
                continue

    def destroy(self):
        self._root()._applylocal_scroll_surfaces.discard(self)
        super().destroy()

    def _content_changed(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _resized(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        self._content_changed()

    def _wheel(self, event):
        widget = event.widget
        try:
            if widget.winfo_toplevel() != self.winfo_toplevel():
                return
            number = getattr(event, 'num', None)
            delta = getattr(event, 'delta', 0)
            if number not in (4, 5) and not delta:
                return
            units = -1 if number == 4 else 1 if number == 5 else (-1 if delta > 0 else 1)
            if number not in (4, 5) and delta:
                units *= max(1, int(abs(delta) / 120))
            if isinstance(widget, tk.Text):
                low, high = widget.yview()
                if (units < 0 and low > 0) or (units > 0 and high < 1):
                    return  # The log's native binding handles its own content.
            parent = widget
            while parent is not None and parent != self.content:
                if isinstance(parent, tk.Canvas) and parent != self.canvas:
                    low, high = parent.yview()
                    if (units < 0 and low > 0) or (units > 0 and high < 1):
                        parent.yview_scroll(units, 'units')
                        return 'break'
                parent = parent.master
            self.canvas.yview_scroll(units * 2, 'units')
            return 'break'
        except tk.TclError:
            return

    @staticmethod
    def _editing(event):
        return event.widget.winfo_class() in {'Entry', 'TEntry', 'TCombobox', 'Text'}

    def _page(self, event, direction):
        if not self._editing(event):
            self.canvas.yview_scroll(direction, 'pages')
            return 'break'

    def _edge(self, event, position):
        if not self._editing(event):
            self.canvas.yview_moveto(position)
            return 'break'

    def reveal(self, widget):
        self.update_idletasks()
        top = widget.winfo_rooty() - self.content.winfo_rooty()
        total = max(1, self.content.winfo_height())
        self.canvas.yview_moveto(max(0, top - 12) / total)
