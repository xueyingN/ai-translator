import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from translate import TranslationError, translate
from translate_history import (
    HistoryError,
    clear_records,
    delete_record,
    export_records,
    load_records,
    save_record,
    search_records,
)


def main():
    window = tk.Tk()
    window.title("AI 翻译器")
    window.geometry("700x760")
    window.minsize(600, 620)

    source_label = tk.Label(window, text="源语言：")
    source_label.pack()

    source_language = ttk.Combobox(
        window,
        values=["中文", "英语", "日语", "韩语"],
        state="readonly",
    )
    source_language.set("中文")
    source_language.pack()

    input_label = tk.Label(window, text="请输入翻译内容")
    input_label.pack()

    source_text = tk.Text(window, height=8, width=60)
    source_text.pack()

    target_label = tk.Label(window, text="目标语言：")
    target_label.pack()

    target_language = ttk.Combobox(
        window,
        values=["中文", "英语", "日语", "韩语"],
        state="readonly",
    )
    target_language.set("英语")
    target_language.pack()

    result_label = tk.Label(window, text="翻译结果：")
    result_label.pack()

    result_text = tk.Text(window, height=8, width=60)
    result_text.pack()

    # 历史面板控件先创建但不 pack，默认隐藏，点击"查看历史"后才显示
    history_label = tk.Label(window, text="翻译历史记录")

    history_frame = tk.Frame(window)

    history_scroll = tk.Scrollbar(history_frame)
    history_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    history_text = tk.Text(
        history_frame,
        height=8,
        yscrollcommand=history_scroll.set,
    )
    history_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    history_scroll.config(command=history_text.yview)
    history_text.config(state=tk.DISABLED)

    # 历史面板是否已显示
    history_visible = False

    def show_history_panel():
        """确保历史面板已显示（pack 到窗口中）。"""
        nonlocal history_visible
        if not history_visible:
            history_label.pack(pady=(10, 0))
            history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
            history_visible = True

    def render_records(records, empty_message="暂无翻译历史"):
        history_text.config(state=tk.NORMAL)
        history_text.delete("1.0", tk.END)
        if not records:
            history_text.insert(tk.END, empty_message)
        else:
            for item in records:
                history_text.insert(
                    tk.END,
                    (
                        f"ID：{item['id']}  【{item['time']}】\n"
                        f"{item['source_language']} → {item['target_language']}\n"
                        f"原文：{item['source']}\n"
                        f"译文：{item['target']}\n"
                        f"{'-' * 30}\n"
                    ),
                )
        history_text.config(state=tk.DISABLED)
        history_text.see(tk.END)

    def load_history():
        show_history_panel()
        try:
            render_records(load_records())
        except HistoryError as exc:
            messagebox.showerror("读取历史失败", str(exc), parent=window)

    def search_history():
        show_history_panel()
        keyword = simpledialog.askstring("搜索历史", "请输入关键词：", parent=window)
        if keyword is None:
            return
        try:
            render_records(search_records(keyword), "没有匹配的历史记录")
        except (HistoryError, ValueError) as exc:
            messagebox.showerror("搜索失败", str(exc), parent=window)

    def delete_history():
        record_id = simpledialog.askinteger(
            "删除历史",
            "请输入要删除的记录 ID：",
            parent=window,
            minvalue=1,
        )
        if record_id is None:
            return
        if not messagebox.askyesno(
            "确认删除",
            f"确定删除 ID 为 {record_id} 的历史记录吗？",
            parent=window,
        ):
            return
        try:
            if delete_record(record_id):
                messagebox.showinfo("删除历史", "记录已删除", parent=window)
                load_history()
            else:
                messagebox.showinfo("删除历史", "未找到该记录", parent=window)
        except (HistoryError, ValueError) as exc:
            messagebox.showerror("删除失败", str(exc), parent=window)

    def clear_history():
        show_history_panel()
        if not messagebox.askyesno(
            "确认清空",
            "确定清空全部翻译历史吗？此操作不能撤销。",
            parent=window,
        ):
            return
        try:
            count = clear_records()
            render_records([])
            messagebox.showinfo("清空历史", f"已清空 {count} 条历史记录", parent=window)
        except HistoryError as exc:
            messagebox.showerror("清空失败", str(exc), parent=window)

    def export_history():
        output_path = filedialog.asksaveasfilename(
            parent=window,
            title="导出翻译历史",
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile="translation_history.csv",
        )
        if not output_path:
            return
        try:
            count = export_records(output_path)
            messagebox.showinfo(
                "导出历史",
                f"已导出 {count} 条历史记录到：\n{output_path}",
                parent=window,
            )
        except FileExistsError:
            messagebox.showerror(
                "导出失败",
                "目标文件已存在。请选择新的文件名，避免覆盖已有文件。",
                parent=window,
            )
        except HistoryError as exc:
            messagebox.showerror("导出失败", str(exc), parent=window)

    def do_translate():
        text = source_text.get("1.0", "end-1c")
        try:
            result = translate(text, source_language.get(), target_language.get())
        except TranslationError as exc:
            result_text.delete("1.0", tk.END)
            result_text.insert("1.0", f"翻译失败：{exc}")
            return

        result_text.delete("1.0", tk.END)
        result_text.insert("1.0", result)
        try:
            save_record(
                source_language.get(),
                target_language.get(),
                text,
                result,
            )
        except HistoryError as exc:
            messagebox.showwarning(
                "历史记录未保存",
                f"翻译已完成，但历史记录未保存：{exc}",
                parent=window,
            )
            return

    translate_button = tk.Button(window, text="开始翻译", command=do_translate)
    translate_button.pack(pady=(5, 0))

    history_buttons = tk.Frame(window)
    history_buttons.pack(pady=5)
    tk.Button(history_buttons, text="查看历史", command=load_history).pack(
        side=tk.LEFT, padx=3
    )
    tk.Button(history_buttons, text="搜索", command=search_history).pack(
        side=tk.LEFT, padx=3
    )
    tk.Button(history_buttons, text="删除单条", command=delete_history).pack(
        side=tk.LEFT, padx=3
    )
    tk.Button(history_buttons, text="清空", command=clear_history).pack(
        side=tk.LEFT, padx=3
    )
    tk.Button(history_buttons, text="导出 CSV", command=export_history).pack(
        side=tk.LEFT, padx=3
    )

    window.mainloop()


if __name__ == "__main__":
    main()
