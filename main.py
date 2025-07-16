import tkinter as tk
from tkinter import messagebox
import os
import json
import webbrowser
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from comfyui import ComfyUISettings, send_workflow, api_system_stats



def auto_close_message(parent, title, message, timeout=1200):
    """
    创建一个在指定时间后自动关闭的消息弹窗，并居中于父窗口。

    Args:
        parent (tk.Toplevel or tk.Tk): 父窗口，弹窗将在此之上居中。
        title (str): 弹窗的标题。
        message (str): 弹窗显示的消息。
        timeout (int, optional): 弹窗显示的毫秒数。默认为 1200ms。
    """
    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.geometry("300x100")
    popup.attributes("-topmost", True)
    
    # 使用ttkbootstrap样式
    ttkb.Label(popup, text=message, padding=(20, 20)).pack(expand=True, fill="both")

    # 计算并设置居中位置
    popup.update_idletasks()
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()
    parent_w = parent.winfo_width()
    parent_h = parent.winfo_height()
    popup_w = popup.winfo_width()
    popup_h = popup.winfo_height()
    x = parent_x + (parent_w - popup_w) // 2
    y = parent_y + (parent_h - popup_h) // 2
    popup.geometry(f"+{x}+{y}")

    popup.after(timeout, popup.destroy)


class DataManager:
    """
    处理所有文件I/O操作，如加载和保存JSON配置文件。
    """
    GENERATED_PROMPTS_FILE = "./prompts/generated_prompts.json"
    PROMPT_PRESETS_FILE = "./prompts/prompt_presets.json"

    @staticmethod
    def load_generated_prompts():
        """从JSON文件加载已生成的prompt串。"""
        if os.path.exists(DataManager.GENERATED_PROMPTS_FILE):
            with open(DataManager.GENERATED_PROMPTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @staticmethod
    def save_generated_prompts(data):
        """将生成的prompt串保存到JSON文件。"""
        with open(DataManager.GENERATED_PROMPTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_prompt_presets():
        """
        从JSON文件加载Prompt预设。
        为了兼容旧格式（值是字符串列表），会自动转换成新的格式（对象列表）。
        """
        default_categories = ["quality", "style", "character", "pose", "extra"]
        data = {cat: [] for cat in default_categories}

        if os.path.exists(DataManager.PROMPT_PRESETS_FILE):
            try:
                with open(DataManager.PROMPT_PRESETS_FILE, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                for cat in default_categories:
                    if cat in loaded_data:
                        # 兼容性检查：如果旧格式是字符串列表，则转换为新格式
                        if loaded_data[cat] and isinstance(loaded_data[cat][0], str):
                            data[cat] = [{"name": v, "value": v} for v in loaded_data[cat]]
                        else:
                            data[cat] = loaded_data[cat]
            except (json.JSONDecodeError, IndexError) as e:
                messagebox.showerror("错误", f"加载 prompt_presets.json失败: {e}")
        return data

    @staticmethod
    def save_prompt_presets(data):
        """将Prompt预设保存到JSON文件。"""
        with open(DataManager.PROMPT_PRESETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class MainApp(ttkb.Window):
    """
    AI绘图预设管理器主应用程序窗口。
    """
    # 定义常量以便于管理
    PROMPT_CATEGORIES = ["quality", "style", "character", "pose"]
    EXTRA_CATEGORY = "extra"
    ALL_CATEGORIES = PROMPT_CATEGORIES + [EXTRA_CATEGORY]
    
    # 定义生成prompt时各部分的拼接顺序
    PROMPT_VALUE_ORDER = ["quality", "style", "character", "pose", "extra"]
    PROMPT_KEY_ORDER = ["character", "pose", "style", "extra", "quality"]

    def __init__(self):
        super().__init__(themename="cosmo")
        self.title("ComfyUI预设管理器")
        self.geometry("900x850")
        
        # --- 状态变量初始化 ---
        self.generated_prompts = DataManager.load_generated_prompts()
        self.prompt_presets = DataManager.load_prompt_presets()
        self.comfyui_settings = ComfyUISettings()

        # Tkinter变量，用于绑定UI控件
        self.prompt_vars = {cat: ttkb.StringVar() for cat in self.PROMPT_CATEGORIES}
        self.comfyui_url_var = ttkb.StringVar(value="http://127.0.0.1:8000/")
        self.comfyui_status_var = ttkb.StringVar(value="尚未检测")
        self.comfyui_preset_var = ttkb.StringVar()

        # 存储UI控件的引用，便于后续访问
        self.prompt_comboboxes = {}
        self.prompt_entries = {}
        self.comfyui_entries = {}
        
        # --- 构建UI界面 ---
        self._build_ui()
        self._initial_load()

    def _build_ui(self):
        """构建主界面，包含多个选项卡。"""
        notebook = ttkb.Notebook(self, bootstyle="primary")
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # 创建各个选项卡
        prompt_tab = self._build_prompt_tab(notebook)
        comfyui_settings_tab = self._build_comfyui_settings_tab(notebook)
        comfyui_connect_tab = self._build_comfyui_connect_tab(notebook)
        about_tab = self._build_about_tab(notebook)
        
        # 将选项卡添加到Notebook
        notebook.add(prompt_tab, text="🎨 Prompt管理")
        notebook.add(comfyui_settings_tab, text="⚙️ ComfyUI设置")
        notebook.add(comfyui_connect_tab, text="🔌 连接ComfyUI")
        notebook.add(about_tab, text="ℹ️ 关于")

    def _initial_load(self):
        """在UI构建完成后，加载初始数据并刷新界面。"""
        self.refresh_generated_listbox()
        self.load_comfyui_presets()
        # 绑定ComfyUI预设下拉菜单的变动事件
        self.comfyui_preset_var.trace_add("write", self.on_comfyui_preset_change)
        # 加载第一个预设（如果存在）
        if self.comfyui_preset_var.get():
            self.load_comfyui_preset(self.comfyui_preset_var.get())

    # ===================================================================
    # UI构建辅助方法
    # ===================================================================
    
    def _build_prompt_tab(self, parent):
        """构建Prompt管理选项卡界面。"""
        tab = ttkb.Frame(parent)
        
        # 左右分区
        left_frame = ttkb.Frame(tab)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right_frame = ttkb.Frame(tab, width=350)
        right_frame.pack(side="right", fill="y")
        right_frame.pack_propagate(False) # 防止right_frame被内部组件撑大或缩小

        # --- 左侧：预设管理 ---
        for cat in self.PROMPT_CATEGORIES:
            self._create_prompt_category_ui(left_frame, cat)
        
        self._create_extra_category_ui(left_frame)

        # --- 右侧：生成与发送 ---
        self._create_generation_ui(right_frame)

        return tab

    def _create_prompt_category_ui(self, parent, cat):
        """为单个prompt类别（如quality, style）创建UI组件。"""
        frame = ttkb.Labelframe(parent, text=f"🎯 {cat.capitalize()} Prompt", padding=10)
        frame.pack(fill="x", pady=5, padx=5)
        frame.grid_columnconfigure(1, weight=1)

        ttkb.Label(frame, text=f"选择{cat}:").grid(row=0, column=0, padx=5, sticky="w")
        
        names = [p["name"] for p in self.prompt_presets[cat]]
        combo = ttkb.Combobox(frame, textvariable=self.prompt_vars[cat], values=names, state="readonly")
        combo.grid(row=0, column=1, padx=5, sticky="ew")
        
        # 绑定事件和存储引用
        combo.bind("<<ComboboxSelected>>", lambda e, c=cat: self.on_prompt_selected(e, c))
        self.prompt_comboboxes[cat] = combo

        name_entry = ttkb.Entry(frame)
        name_entry.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        val_entry = ttkb.Entry(frame)
        val_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        # --- FIX START ---
        # 修正：必须先将Entry控件存入字典...
        self.prompt_entries[cat] = (name_entry, val_entry)
        
        # ...然后再调用on_prompt_selected，因为它会使用这个字典
        if names:
            self.prompt_vars[cat].set(names[0])
            self.on_prompt_selected(None, cat)
        # --- FIX END ---
        
        # 按钮
        btn_frame = ttkb.Frame(frame)
        btn_frame.grid(row=0, column=2, rowspan=2, padx=5)
        ttkb.Button(btn_frame, text="新增", command=lambda c=cat: self.add_prompt(c), bootstyle="success-outline").pack(fill="x", pady=1)
        ttkb.Button(btn_frame, text="修改", command=lambda c=cat: self.edit_prompt(c), bootstyle="warning-outline").pack(fill="x", pady=1)
        ttkb.Button(btn_frame, text="删除", command=lambda c=cat: self.delete_prompt(c), bootstyle="danger-outline").pack(fill="x", pady=1)

    def _create_extra_category_ui(self, parent):
        """为'extra'类别（多选）创建UI组件。"""
        cat = self.EXTRA_CATEGORY
        frame = ttkb.Labelframe(parent, text="🧩 Extra Prompt (可多选)", padding=10)
        frame.pack(fill="x", pady=5, padx=5)
        frame.grid_columnconfigure(1, weight=1)

        # ... (Listbox 和 Scrollbar 的创建代码不变) ...
        listbox_frame = ttkb.Frame(frame)
        listbox_frame.grid(row=0, column=0, rowspan=2, sticky="nswe", padx=5)
        self.extra_listbox = tk.Listbox(listbox_frame, selectmode="multiple", height=6, exportselection=False)
        self.extra_listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttkb.Scrollbar(listbox_frame, orient="vertical", command=self.extra_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.extra_listbox.config(yscrollcommand=scrollbar.set)
        
        for p in self.prompt_presets[cat]:
            self.extra_listbox.insert("end", p["name"])
        self.extra_listbox.bind("<<ListboxSelect>>", lambda e, c=cat: self.on_prompt_selected(e, c))

        name_entry = ttkb.Entry(frame)
        name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        val_entry = ttkb.Entry(frame)
        val_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # --- FIX ---
        # 修正：将这行提前，保持逻辑一致
        self.prompt_entries[cat] = (name_entry, val_entry)
        
        # 按钮
        btn_frame = ttkb.Frame(frame)
        btn_frame.grid(row=0, column=2, rowspan=2, padx=5)
        ttkb.Button(btn_frame, text="新增", command=lambda c=cat: self.add_prompt(c), bootstyle="success-outline").pack(fill="x", pady=1)
        ttkb.Button(btn_frame, text="修改", command=lambda c=cat: self.edit_prompt(c), bootstyle="warning-outline").pack(fill="x", pady=1)
        ttkb.Button(btn_frame, text="删除", command=lambda c=cat: self.delete_prompt(c), bootstyle="danger-outline").pack(fill="x", pady=1)

    def _create_generation_ui(self, parent):
        """创建右侧的prompt生成、预览和发送区域UI。"""
        ttkb.Label(parent, text="预设串列表:", font=("", 12, "bold")).pack(anchor="w")

        list_frame = ttkb.Frame(parent)
        list_frame.pack(fill="x", expand=False, pady=5)
        self.generated_listbox = tk.Listbox(list_frame, height=12, selectmode="extended", exportselection=False)
        self.generated_listbox.pack(side="left", fill="x", expand=True)
        scrollbar = ttkb.Scrollbar(list_frame, orient="vertical", command=self.generated_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.generated_listbox.config(yscrollcommand=scrollbar.set)
        self.generated_listbox.bind("<<ListboxSelect>>", self.on_generated_select)

        ttkb.Label(parent, text="Prompt预览:", font=("", 12, "bold")).pack(anchor="w", pady=(10,0))
        
        text_frame = ttkb.Frame(parent)
        text_frame.pack(fill="both", expand=True, pady=5)
        self.generated_prompt_text = tk.Text(text_frame, height=10, wrap="word", relief="solid", borderwidth=1)
        self.generated_prompt_text.pack(side="left", fill="both", expand=True)
        text_scrollbar = ttkb.Scrollbar(text_frame, orient="vertical", command=self.generated_prompt_text.yview)
        text_scrollbar.pack(side="right", fill="y")
        self.generated_prompt_text.config(yscrollcommand=text_scrollbar.set)

        ttkb.Button(parent, text="🎯 生成Prompt预设串", command=self.generate_prompt_string, bootstyle="primary").pack(fill="x", pady=5)
        ttkb.Button(parent, text="🗑 删除选中Prompt", command=self.delete_generated_prompt, bootstyle="danger").pack(fill="x", pady=5)
        ttkb.Button(parent, text="📤 发送选中Prompt", command=self.send_selected_prompt, bootstyle="success").pack(fill="x")

    def _build_comfyui_settings_tab(self, parent):
        """构建ComfyUI设置选项卡界面。"""
        tab = ttkb.Frame(parent)
        
        top_frame = ttkb.Frame(tab)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        ttkb.Label(top_frame, text="选择预设:").pack(side="left")
        self.comfyui_menu = ttkb.OptionMenu(top_frame, self.comfyui_preset_var, "无预设")
        self.comfyui_menu.pack(side="left", padx=5)
        
        ttkb.Button(top_frame, text="新建", command=self.new_comfyui_preset).pack(side="left", padx=5)
        ttkb.Button(top_frame, text="保存", command=self.save_comfyui_preset).pack(side="left", padx=5)
        ttkb.Button(top_frame, text="删除", command=self.delete_comfyui_preset).pack(side="left", padx=5)

        fields = [
            ("presets_name", "预设名称"), ("checkpoint", "Checkpoint"), ("lora", "LoRA"),
            ("latent_width", "宽度"), ("latent_height", "高度"),
            ("batch_size", "Batch大小"), ("seed", "Seed"),
            ("steps", "Steps"), ("cfg", "CFG Scale"),
        ]

        for key, label in fields:
            row = ttkb.Frame(tab)
            row.pack(fill="x", padx=10, pady=4)
            ttkb.Label(row, text=label, width=12).pack(side="left")
            entry = ttkb.Entry(row)
            entry.pack(side="left", fill="x", expand=True)
            self.comfyui_entries[key] = entry
        
        return tab

    def _build_comfyui_connect_tab(self, parent):
        """构建ComfyUI连接测试选项卡界面。"""
        tab = ttkb.Frame(parent)
        
        frame = ttkb.Labelframe(tab, text="连接设置", padding=15)
        frame.pack(padx=10, pady=10, fill="x")

        ttkb.Label(frame, text="ComfyUI 地址:").pack(side="left", padx=(0, 5))
        entry = ttkb.Entry(frame, textvariable=self.comfyui_url_var)
        entry.pack(side="left", fill="x", expand=True, padx=5)
        
        ttkb.Button(frame, text="检测连接", command=self.check_comfyui_connection, bootstyle="info-outline").pack(side="left", padx=5)

        self.status_label = ttkb.Label(tab, textvariable=self.comfyui_status_var, bootstyle="secondary", font=("", 10))
        self.status_label.pack(pady=10)

        return tab

    def _build_about_tab(self, parent):
        """构建关于选项卡界面。"""
        tab = ttkb.Frame(parent, padding=20)
        
        github_url = "https://github.com/Lisanjin"
        
        ttkb.Label(tab, text="AI绘图预设管理器", font=("", 16, "bold")).pack(pady=(20, 5))
        ttkb.Label(tab, text="by 小三金", font=("", 12)).pack(pady=5)
        
        link_label = ttkb.Label(tab, text=github_url, foreground="blue", cursor="hand2")
        link_label.pack(pady=20)
        link_label.bind("<Button-1>", lambda e: webbrowser.open_new(github_url))

        return tab

    # ===================================================================
    # 事件处理和业务逻辑
    # ===================================================================

    def on_prompt_selected(self, event, category):
        """当一个prompt预设被选中时，更新对应的输入框内容。"""
        if category == self.EXTRA_CATEGORY:
            selections = self.extra_listbox.curselection()
            if not selections: return
            selected_name = self.extra_listbox.get(selections[0])
        else:
            selected_name = self.prompt_vars[category].get()

        for preset in self.prompt_presets[category]:
            if preset["name"] == selected_name:
                name_entry, val_entry = self.prompt_entries[category]
                name_entry.delete(0, tk.END)
                name_entry.insert(0, preset["name"])
                val_entry.delete(0, tk.END)
                val_entry.insert(0, preset["value"])
                break
    
    def _get_selected_preset_name(self, category):
        """辅助方法，获取指定类别中当前选中的预设名称。"""
        if category == self.EXTRA_CATEGORY:
            selections = self.extra_listbox.curselection()
            return [self.extra_listbox.get(i) for i in selections] if selections else []
        else:
            return self.prompt_vars[category].get()

    def add_prompt(self, category):
        """新增一个prompt预设。"""
        name_entry, val_entry = self.prompt_entries[category]
        name = name_entry.get().strip()
        value = val_entry.get().strip()

        if not name or not value:
            messagebox.showwarning("输入无效", "名称和内容都不能为空。")
            return
        if any(p["name"] == name for p in self.prompt_presets[category]):
            messagebox.showwarning("名称重复", "该名称的预设已存在。")
            return

        self.prompt_presets[category].append({"name": name, "value": value})
        DataManager.save_prompt_presets(self.prompt_presets)
        self.refresh_prompt_ui(category)
        auto_close_message(self, "成功", f"已新增预设: {name}")

    def edit_prompt(self, category):
        """修改选中的prompt预设。"""
        selected_names = self._get_selected_preset_name(category)
        if not selected_names:
            messagebox.showwarning("未选择", "请先选择一个要修改的预设。")
            return
        # 对于非多选，列表只有一个元素
        selected_name = selected_names if category != self.EXTRA_CATEGORY else selected_names[0]

        name_entry, val_entry = self.prompt_entries[category]
        new_name = name_entry.get().strip()
        new_value = val_entry.get().strip()
        
        if not new_name or not new_value:
            messagebox.showwarning("输入无效", "名称和内容都不能为空。")
            return

        # 检查新名称是否与其它预设冲突
        if new_name != selected_name and any(p["name"] == new_name for p in self.prompt_presets[category]):
            messagebox.showwarning("名称重复", "修改后的名称与其它预设冲突。")
            return
        
        for i, preset in enumerate(self.prompt_presets[category]):
            if preset["name"] == selected_name:
                self.prompt_presets[category][i] = {"name": new_name, "value": new_value}
                DataManager.save_prompt_presets(self.prompt_presets)
                self.refresh_prompt_ui(category, new_name)
                auto_close_message(self, "成功", f"已修改预设: {new_name}")
                return

    def delete_prompt(self, category):
        """删除选中的prompt预设。"""
        selected_names = self._get_selected_preset_name(category)
        if not selected_names:
            messagebox.showwarning("未选择", "请先选择一个要删除的预设。")
            return

        # 对于多选，可以一次删除多个
        if not messagebox.askyesno("确认删除", f"确定要删除选中的 {len(selected_names)} 个预设吗？"):
            return

        initial_count = len(self.prompt_presets[category])
        self.prompt_presets[category] = [p for p in self.prompt_presets[category] if p["name"] not in selected_names]
        
        if len(self.prompt_presets[category]) < initial_count:
            DataManager.save_prompt_presets(self.prompt_presets)
            self.refresh_prompt_ui(category)
            auto_close_message(self, "成功", "选中的预设已被删除。")

    def refresh_prompt_ui(self, category, new_selection=None):
        """刷新指定类别的UI（Combobox或Listbox）。"""
        if category == self.EXTRA_CATEGORY:
            self.extra_listbox.delete(0, tk.END)
            for p in self.prompt_presets[category]:
                self.extra_listbox.insert("end", p["name"])
        else:
            combo = self.prompt_comboboxes[category]
            names = [p["name"] for p in self.prompt_presets[category]]
            combo['values'] = names
            
            if new_selection and new_selection in names:
                self.prompt_vars[category].set(new_selection)
            elif names:
                self.prompt_vars[category].set(names[0])
            else:
                self.prompt_vars[category].set("")
            self.on_prompt_selected(None, category) # 刷新后更新输入框

    def generate_prompt_string(self):
        """根据当前选择生成prompt key和value，并保存。"""
        # 1. 组合Prompt值 (按指定顺序)
        prompt_parts = []
        for cat in self.PROMPT_VALUE_ORDER:
            if cat == self.EXTRA_CATEGORY:
                selected_indices = self.extra_listbox.curselection()
                for i in selected_indices:
                    name = self.extra_listbox.get(i)
                    value = next((p["value"] for p in self.prompt_presets[cat] if p["name"] == name), None)
                    if value: prompt_parts.append(value.strip(","))
            else:
                selected_name = self.prompt_vars[cat].get()
                if selected_name:
                    value = next((p["value"] for p in self.prompt_presets[cat] if p["name"] == selected_name), None)
                    if value: prompt_parts.append(value.strip(","))
        
        full_prompt = ", ".join(filter(None, prompt_parts))

        # 2. 组合Prompt Key (按另一指定顺序)
        key_parts = []
        for cat in self.PROMPT_KEY_ORDER:
            if cat == self.EXTRA_CATEGORY:
                selected_indices = self.extra_listbox.curselection()
                if selected_indices:
                    extras = [self.extra_listbox.get(i) for i in selected_indices]
                    key_parts.append("_".join(extras)) # 用下划线连接多个extra名称
            else:
                key_parts.append(self.prompt_vars[cat].get())
        
        final_key = "-".join(filter(None, key_parts))
        
        if not final_key:
            messagebox.showwarning("无法生成", "请至少选择一个Prompt预设。")
            return

        # 3. 保存和刷新UI
        self.generated_prompts[final_key] = full_prompt
        DataManager.save_generated_prompts(self.generated_prompts)
        self.refresh_generated_listbox()

        # 选中刚生成的项
        try:
            idx = list(self.generated_prompts.keys()).index(final_key)
            self.generated_listbox.selection_clear(0, tk.END)
            self.generated_listbox.selection_set(idx)
            self.generated_listbox.see(idx)
            self.on_generated_select(None)
            auto_close_message(self, "成功", f"已生成Prompt: {final_key}")
        except ValueError:
            pass # 应该不会发生

    def delete_generated_prompt(self):
        """删除选中的已生成prompt（支持多选）。"""
        sels = self.generated_listbox.curselection()
        if not sels:
            messagebox.showwarning("未选择", "请先从列表中选择要删除的Prompt。")
            return
        
        keys = [self.generated_listbox.get(i) for i in sels]
        if not messagebox.askyesno("确认删除", f"确定要删除以下 {len(keys)} 项？\n" + "\n".join(keys)):
            return

        for key in keys:
            self.generated_prompts.pop(key, None)
        DataManager.save_generated_prompts(self.generated_prompts)
        self.refresh_generated_listbox()
        self.generated_prompt_text.delete("1.0", tk.END)
        auto_close_message(self, "删除成功", f"已删除 {len(keys)} 个Prompt。")

    def refresh_generated_listbox(self):
        """刷新右侧的已生成prompt列表。"""
        self.generated_listbox.delete(0, tk.END)
        for key in self.generated_prompts.keys():
            self.generated_listbox.insert(tk.END, key)

    def on_generated_select(self, event):
        """当已生成prompt被选中时，在预览框中显示其内容。"""
        sel = self.generated_listbox.curselection()
        if sel:
            key = self.generated_listbox.get(sel[0])
            full_prompt = self.generated_prompts.get(key, "")
            self.generated_prompt_text.delete("1.0", tk.END)
            self.generated_prompt_text.insert("1.0", full_prompt)

    def send_selected_prompt(self):
        """将选中的prompt发送到ComfyUI（支持多选）。"""
        if self.comfyui_status_var.get().startswith("❌"):
            messagebox.showerror("连接失败", "无法发送，请先在'连接ComfyUI'选项卡中确保连接成功。")
            return

        sels = self.generated_listbox.curselection()
        if not sels:
            auto_close_message(self, "提示", "请先选择一个或多个Prompt发送")
            return

        count = 0
        for i in sels:
            key = self.generated_listbox.get(i)
            prompt_text = self.generated_prompts.get(key, "")
            if prompt_text:
                send_workflow(self.comfyui_url_var.get(), self.comfyui_settings, prompt_text)
                count += 1

        auto_close_message(self, "发送成功", f"已发送 {count} 个Prompt")

    # --- ComfyUI 设置相关方法 ---
    def load_comfyui_presets(self):
        """加载所有ComfyUI预设并更新下拉菜单。"""
        presets = ComfyUISettings.list_presets()
        menu = self.comfyui_menu["menu"]
        menu.delete(0, "end")
        
        if presets:
            for name in presets:
                menu.add_command(label=name, command=lambda n=name: self.comfyui_preset_var.set(n))
            self.comfyui_preset_var.set(presets[0])
        else:
            self.comfyui_preset_var.set("无预设")
            self.new_comfyui_preset()

    def load_comfyui_preset(self, name):
        """加载指定的ComfyUI预设并更新UI。"""
        self.comfyui_settings = ComfyUISettings.load(name)
        for key, entry in self.comfyui_entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, str(getattr(self.comfyui_settings, key, '')))

    def on_comfyui_preset_change(self, *args):
        """当ComfyUI预设下拉菜单变化时触发。"""
        name = self.comfyui_preset_var.get()
        if name and name != "无预设":
            self.load_comfyui_preset(name)

    def new_comfyui_preset(self):
        """清空输入框以创建新的ComfyUI预设。"""
        self.comfyui_settings = ComfyUISettings(name="new_preset")
        self.load_comfyui_preset("new_preset") # 这会清空UI
        self.comfyui_entries["presets_name"].focus_set()

    def save_comfyui_preset(self):
        """保存当前UI中的ComfyUI设置。"""
        for key, entry in self.comfyui_entries.items():
            value = entry.get()
            # 类型转换
            if key in ["latent_width", "latent_height", "batch_size", "steps", "seed"]:
                try: value = int(value)
                except ValueError: value = 0
            elif key == "cfg":
                try: value = float(value)
                except ValueError: value = 7.5
            setattr(self.comfyui_settings, key, value)
        
        if not self.comfyui_settings.presets_name:
            messagebox.showwarning("需要名称", "预设名称不能为空。")
            return
            
        self.comfyui_settings.save()
        self.load_comfyui_presets() # 刷新列表
        self.comfyui_preset_var.set(self.comfyui_settings.presets_name) # 选中刚保存的
        auto_close_message(self, "成功", "ComfyUI设置已保存！")

    def delete_comfyui_preset(self):
        """删除当前选中的ComfyUI预设。"""
        name = self.comfyui_preset_var.get()
        if not name or name == "无预设":
            messagebox.showwarning("未选择", "没有选择要删除的预设。")
            return
        
        if messagebox.askyesno("确认删除", f"确定要删除ComfyUI预设 '{name}' 吗？"):
            filepath = os.path.join(ComfyUISettings.SETTINGS_DIR, f"{name}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
                self.load_comfyui_presets()
                auto_close_message(self, "成功", f"已删除预设：{name}")

    # --- ComfyUI 连接相关方法 ---
    def check_comfyui_connection(self):
        """检测与ComfyUI服务器的连接。"""
        url = self.comfyui_url_var.get().strip()
        if not url:
            self.comfyui_status_var.set("❌ URL不能为空")
            self.status_label.config(bootstyle="danger")
            return

        if api_system_stats(url):
            self.comfyui_status_var.set("✅ 成功连接到 ComfyUI")
            self.status_label.config(bootstyle="success")
        else:
            self.comfyui_status_var.set("❌ 无法连接到 ComfyUI")
            self.status_label.config(bootstyle="danger")

# nuitka --mingw64 --enable-plugin=tk-inter --standalone --onefile --show-progress --output-filename=comfyui_presets_util.exe main.py
if __name__ == "__main__":
    app = MainApp()
    app.mainloop()