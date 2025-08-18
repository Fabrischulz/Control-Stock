import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import requests
import tkinter.font as tkFont
from PIL import Image, ImageTk
import threading
import time

DB_NAME = "stock.db"

def get_usd_price():
    try:
        # Consulta a la API pública de Bluelytics
        response = requests.get("https://api.bluelytics.com.ar/v2/latest")
        data = response.json()
        # Usar el valor de venta oficial (Banco Nación)
        return data["oficial"]["value_sell"]
    except Exception:
        return 0

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        costo_real REAL,
        costo_comprador REAL,
        iva REAL,
        en_dolares INTEGER,
        cantidad INTEGER DEFAULT 0,
        min_stock INTEGER DEFAULT 1
    )''')
    # Tabla para historial de eliminados
    c.execute('''CREATE TABLE IF NOT EXISTS eliminados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        fecha_eliminado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    try:
        c.execute("ALTER TABLE productos ADD COLUMN min_stock INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def add_producto(nombre, costo_real, costo_comprador, iva, en_dolares, usd_price, cantidad, min_stock):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Ya recibes los valores en pesos, NO vuelvas a multiplicar por usd_price
    c.execute("INSERT INTO productos (nombre, costo_real, costo_comprador, iva, en_dolares, cantidad, min_stock) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (nombre, costo_real, costo_comprador, iva, en_dolares, cantidad, min_stock))
    conn.commit()
    conn.close()

def get_productos():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM productos")
    productos = c.fetchall()
    conn.close()
    return productos

def descontar_stock(producto_id, cantidad):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT cantidad FROM productos WHERE id=?", (producto_id,))
    actual = c.fetchone()
    if actual and actual[0] >= cantidad:
        c.execute("UPDATE productos SET cantidad = cantidad - ? WHERE id=?", (cantidad, producto_id))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def eliminar_producto(producto_id, nombre):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Guarda en historial
    c.execute("INSERT INTO eliminados (nombre) VALUES (?)", (nombre,))
    # Elimina de productos
    c.execute("DELETE FROM productos WHERE id=?", (producto_id,))
    conn.commit()
    conn.close()

def calcular_iva_total():
    productos = get_productos()
    total_iva = 0
    for p in productos:
        # p[3] es costo_comprador, p[4] es iva
        total_iva += p[3] * (p[4] / 100)
    return total_iva

class StockApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Control de Stock")
        self.usd_price = get_usd_price()

        # Paleta marina
        self.bg_main = "#e0f7fa"      # celeste claro
        self.bg_frame = "#b2ebf2"     # celeste agua
        self.bg_tree = "#80deea"      # celeste más fuerte
        self.bg_button = "#4dd0e1"    # azul agua
        self.bg_button2 = "#26c6da"   # azul más fuerte
        self.bg_alert = "#b3e5fc"     # celeste para alertas
        self.fg_main = "#01579b"      # azul oscuro
        self.fg_button = "#004d40"    # verde agua oscuro

        self.setup_ui()
        self.refresh_table()

    def setup_ui(self):
        # No cambies el fondo general ni de los frames
        style = ttk.Style()
        style.theme_use('clam')

        # Solo botones con colores marinos
        style.configure("Mar.TButton",
                        background=self.bg_button,
                        foreground=self.fg_button,
                        font=('Arial', 11, 'bold'),
                        borderwidth=1)
        style.map("Mar.TButton",
                  background=[('active', self.bg_button2), ('pressed', self.bg_button2)])

        frame = ttk.Frame(self.root)
        frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Scrollbar vertical para la tabla
        tree_scroll = ttk.Scrollbar(frame, orient="vertical")
        tree_scroll.pack(side="right", fill="y")

        self.tree = ttk.Treeview(
            frame,
            columns=("Nombre", "Precio de Compra", "Precio de Venta", "IVA (%)", "En Dólares", "Cantidad"),
            show="headings",
            yscrollcommand=tree_scroll.set
        )
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="center", stretch=tk.YES)
        self.tree.pack(fill="x", expand=True, pady=5)

        # IVA total y dólar (sin fondo personalizado)
        self.iva_label = ttk.Label(frame, text="IVA acumulado: $0.00", font=('Arial', 11, 'bold'))
        self.iva_label.pack(pady=5, fill="x")
        self.usd_label = ttk.Label(frame, text=f"Precio del dólar: ${self.usd_price:.2f}", font=('Arial', 11, 'bold'))
        self.usd_label.pack(pady=5, fill="x")

        # Agrupa los botones de a 3
        botones1 = ttk.Frame(frame)
        botones1.pack(pady=5)
        add_btn = ttk.Button(botones1, text="Agregar Producto", command=self.open_add_window, style="Mar.TButton")
        add_btn.pack(side="left", padx=2)
        compra_btn = ttk.Button(botones1, text="Registrar Compra", command=self.open_compra_window, style="Mar.TButton")
        compra_btn.pack(side="left", padx=2)
        agregar_stock_btn = ttk.Button(botones1, text="Agregar Stock", command=self.open_agregar_stock_window, style="Mar.TButton")
        agregar_stock_btn.pack(side="left", padx=2)

        botones2 = ttk.Frame(frame)
        botones2.pack(pady=5)
        eliminar_btn = ttk.Button(botones2, text="Eliminar Producto", command=self.eliminar_producto, style="Mar.TButton")
        eliminar_btn.pack(side="left", padx=2)
        salir_btn = ttk.Button(botones2, text="Salir", command=self.root.quit, style="Mar.TButton")
        salir_btn.pack(side="left", padx=2)

        # NUEVO: Botones para modificar precios
        botones3 = ttk.Frame(frame)
        botones3.pack(pady=5)
        mod_precio_compra_btn = ttk.Button(botones3, text="Modificar precio de compra", command=self.modificar_precio_compra, style="Mar.TButton")
        mod_precio_compra_btn.pack(side="left", padx=2)
        # Elimina el botón de modificar precio de venta
        # mod_precio_venta_btn = ttk.Button(botones3, text="Modificar precio de venta", command=self.modificar_precio_venta, style="Mar.TButton")
        # mod_precio_venta_btn.pack(side="left", padx=2)

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        productos = get_productos()
        for p in productos:
            stock_str = str(p[6])
            if len(p) > 7 and p[6] < p[7]:
                stock_str = f"{p[6]} ⚠️ (MINIMO STOCK EN FALTA!!!)"
            values = (p[1], f"${p[2]:.2f}", f"${p[3]:.2f}", f"{p[4]}%", "Sí" if p[5] else "No", stock_str)
            self.tree.insert("", "end", values=values)
        self.iva_label.config(text=f"IVA acumulado: ${calcular_iva_total():.2f}")
        self.usd_label.config(text=f"Precio del dólar: ${self.usd_price:.2f}")

        # Ajusta el ancho de las columnas al contenido
        self.tree.update()
        for col in self.tree["columns"]:
            self.tree.column(col, width=tkFont.Font().measure(col))
            for item in self.tree.get_children():
                cell_value = self.tree.set(item, col)
                width = tkFont.Font().measure(cell_value)
                if self.tree.column(col, 'width') < width:
                    self.tree.column(col, width=width)

    def open_add_window(self):
        win = tk.Toplevel(self.root)
        win.title("Agregar Producto")

        ttk.Label(win, text="Nombre:").grid(row=0, column=0)
        nombre_entry = ttk.Entry(win)
        nombre_entry.grid(row=0, column=1)

        ttk.Label(win, text="Precio de Compra:").grid(row=1, column=0)
        costo_real_entry = ttk.Entry(win)
        costo_real_entry.grid(row=1, column=1)

        ttk.Label(win, text="Moneda:").grid(row=2, column=0)
        moneda_var = tk.StringVar(value="Pesos")
        moneda_combo = ttk.Combobox(win, textvariable=moneda_var, values=["Pesos", "Dólar"], state="readonly")
        moneda_combo.grid(row=2, column=1)

        ttk.Label(win, text="IVA (%):").grid(row=3, column=0)
        iva_entry = ttk.Entry(win)
        iva_entry.insert(0, "21")
        iva_entry.grid(row=3, column=1)

        ttk.Label(win, text="Cantidad:").grid(row=4, column=0)
        cantidad_entry = ttk.Entry(win)
        cantidad_entry.insert(0, "1")
        cantidad_entry.grid(row=4, column=1)

        ttk.Label(win, text="Mínima cantidad de stock:").grid(row=5, column=0)
        min_stock_entry = ttk.Entry(win)
        min_stock_entry.insert(0, "1")
        min_stock_entry.grid(row=5, column=1)

        # Etiqueta para mostrar el precio de venta calculado
        precio_venta_var = tk.StringVar(value="$0.00")
        ttk.Label(win, text="Precio de Venta:").grid(row=6, column=0)
        precio_venta_label = ttk.Label(win, textvariable=precio_venta_var)
        precio_venta_label.grid(row=6, column=1)

        def actualizar_precio_venta(*args):
            try:
                costo_real = float(costo_real_entry.get())
                moneda = moneda_var.get()
                usd_price = self.usd_price
                if moneda == "Dólar":
                    precio_compra_pesos = costo_real * usd_price
                    precio_venta = precio_compra_pesos * 1.5  # compra + 50%
                else:
                    precio_venta = costo_real * 1.8  # compra + 80%
                precio_venta_var.set(f"${precio_venta:.2f}")
            except Exception:
                precio_venta_var.set("$0.00")

        costo_real_entry.bind("<KeyRelease>", actualizar_precio_venta)
        moneda_combo.bind("<<ComboboxSelected>>", actualizar_precio_venta)

        def agregar():
            try:
                nombre = nombre_entry.get()
                costo_real = float(costo_real_entry.get())
                iva = float(iva_entry.get())
                cantidad = int(cantidad_entry.get())
                min_stock = int(min_stock_entry.get())
                moneda = moneda_var.get()
                usd_price = self.usd_price
                if not nombre:
                    raise ValueError("Nombre vacío")
                if moneda == "Dólar":
                    en_dolares = 1
                    costo_real_db = costo_real * usd_price
                    costo_comprador = costo_real_db * 1.5
                else:
                    en_dolares = 0
                    costo_real_db = costo_real
                    costo_comprador = costo_real * 1.8
                add_producto(nombre, costo_real_db, costo_comprador, iva, en_dolares, usd_price, cantidad, min_stock)
                win.destroy()
                self.refresh_table()
            except Exception as e:
                messagebox.showerror("Error", f"Datos inválidos: {e}")

        ttk.Button(win, text="Agregar", command=agregar).grid(row=7, columnspan=2, pady=5)

    def open_compra_window(self):
        win = tk.Toplevel(self.root)
        win.title("Registrar Compra")

        ttk.Label(win, text="Seleccione producto:").grid(row=0, column=0)
        productos = get_productos()
        nombres = [f"{p[1]} (Stock: {p[6]})" for p in productos]
        producto_var = tk.StringVar()
        producto_combo = ttk.Combobox(win, values=nombres, state="readonly", textvariable=producto_var)
        producto_combo.grid(row=0, column=1)

        ttk.Label(win, text="Cantidad a comprar:").grid(row=1, column=0)
        cantidad_entry = ttk.Entry(win)
        cantidad_entry.insert(0, "1")
        cantidad_entry.grid(row=1, column=1)

        def registrar():
            try:
                idx = producto_combo.current()
                if idx == -1:
                    raise ValueError("Seleccione un producto")
                producto_id = productos[idx][0]
                cantidad = int(cantidad_entry.get())
                if cantidad <= 0:
                    raise ValueError("Cantidad inválida")
                if descontar_stock(producto_id, cantidad):
                    messagebox.showinfo("Éxito", "Compra registrada y stock actualizado.")
                    win.destroy()
                    self.refresh_table()
                else:
                    messagebox.showerror("Error", "Stock insuficiente.")
            except Exception as e:
                messagebox.showerror("Error", f"Datos inválidos: {e}")

        ttk.Button(win, text="Registrar", command=registrar).grid(row=2, columnspan=2, pady=5)

    def open_agregar_stock_window(self):
        win = tk.Toplevel(self.root)
        win.title("Agregar Stock")

        ttk.Label(win, text="Seleccione producto:").grid(row=0, column=0)
        productos = get_productos()
        nombres = [f"{p[1]} (Stock: {p[6]})" for p in productos]
        producto_var = tk.StringVar()
        producto_combo = ttk.Combobox(win, values=nombres, state="readonly", textvariable=producto_var)
        producto_combo.grid(row=0, column=1)

        ttk.Label(win, text="Cantidad a agregar:").grid(row=1, column=0)
        cantidad_entry = ttk.Entry(win)
        cantidad_entry.insert(0, "1")
        cantidad_entry.grid(row=1, column=1)

        def agregar_stock():
            try:
                idx = producto_combo.current()
                if idx == -1:
                    raise ValueError("Seleccione un producto")
                producto_id = productos[idx][0]
                cantidad = int(cantidad_entry.get())
                if cantidad <= 0:
                    raise ValueError("Cantidad inválida")
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("UPDATE productos SET cantidad = cantidad + ? WHERE id=?", (cantidad, producto_id))
                conn.commit()
                conn.close()
                messagebox.showinfo("Éxito", "Stock actualizado.")
                win.destroy()
                self.refresh_table()
            except Exception as e:
                messagebox.showerror("Error", f"Datos inválidos: {e}")

        ttk.Button(win, text="Agregar", command=agregar_stock).grid(row=2, columnspan=2, pady=5)

    def eliminar_cliente(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("Error", "Seleccione un producto para eliminar.")
            return
        item = self.tree.item(selected[0])
        nombre = item["values"][0]
        productos = get_productos()
        # Busca el producto por nombre y cantidad para obtener el id
        for p in productos:
            if p[1] == nombre:
                producto_id = p[0]
                break
        else:
            messagebox.showerror("Error", "No se encontró el producto.")
            return
        if messagebox.askyesno("Confirmar", f"¿Eliminar '{nombre}'?"):
            eliminar_producto(producto_id, nombre)
            self.refresh_table()
            messagebox.showinfo("Eliminado", f"'{nombre}' fue eliminado y registrado en historial.")

    def eliminar_producto(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("Error", "Seleccione un producto para eliminar.")
            return
        item = self.tree.item(selected[0])
        nombre = item["values"][0]
        productos = get_productos()
        # Busca el producto por nombre y cantidad para obtener el id
        for p in productos:
            if p[1] == nombre:
                producto_id = p[0]
                break
        else:
            messagebox.showerror("Error", "No se encontró el producto.")
            return
        if messagebox.askyesno("Confirmar", f"¿Eliminar '{nombre}'?"):
            eliminar_producto(producto_id, nombre)
            self.refresh_table()
            messagebox.showinfo("Eliminado", f"'{nombre}' fue eliminado y registrado en historial.")

    def modificar_precio_compra(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showerror("Error", "Seleccione un producto para modificar.")
            return
        item = self.tree.item(selected[0])
        nombre = item["values"][0]
        productos = get_productos()
        for p in productos:
            if p[1] == nombre:
                producto_id = p[0]
                precio_actual = p[2]
                en_dolares = p[5]
                usd_price = self.usd_price
                break
        else:
            messagebox.showerror("Error", "No se encontró el producto.")
            return

        win = tk.Toplevel(self.root)
        win.title("Modificar precio de compra")
        ttk.Label(win, text=f"Producto: {nombre}").grid(row=0, column=0, columnspan=2)
        ttk.Label(win, text="Nuevo precio de compra:").grid(row=1, column=0)
        precio_entry = ttk.Entry(win)
        precio_entry.insert(0, f"{precio_actual:.2f}")
        precio_entry.grid(row=1, column=1)

        # Etiqueta para mostrar el nuevo precio de venta calculado
        precio_venta_var = tk.StringVar(value="$0.00")
        ttk.Label(win, text="Nuevo precio de venta:").grid(row=2, column=0)
        precio_venta_label = ttk.Label(win, textvariable=precio_venta_var)
        precio_venta_label.grid(row=2, column=1)

        def actualizar_precio_venta(*args):
            try:
                nuevo_precio = float(precio_entry.get())
                if en_dolares:
                    precio_venta = nuevo_precio * usd_price * 1.5
                else:
                    precio_venta = nuevo_precio * 1.8
                precio_venta_var.set(f"${precio_venta:.2f}")
            except Exception:
                precio_venta_var.set("$0.00")

        precio_entry.bind("<KeyRelease>", actualizar_precio_venta)
        actualizar_precio_venta()

        def guardar():
            try:
                nuevo_precio = float(precio_entry.get())
                if en_dolares:
                    nuevo_precio_venta = nuevo_precio * usd_price * 1.5
                else:
                    nuevo_precio_venta = nuevo_precio * 1.8
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("UPDATE productos SET costo_real=?, costo_comprador=? WHERE id=?", (nuevo_precio, nuevo_precio_venta, producto_id))
                conn.commit()
                conn.close()
                win.destroy()
                self.refresh_table()
                messagebox.showinfo("Éxito", "Precio de compra y venta modificados.")
            except Exception as e:
                messagebox.showerror("Error", f"Datos inválidos: {e}")

        ttk.Button(win, text="Guardar", command=guardar).grid(row=3, columnspan=2, pady=5)

def mostrar_splash():
    splash = tk.Tk()
    splash.overrideredirect(True)
    splash.geometry("400x300+500+200")  # Ajusta el tamaño y posición si lo deseas

    img = Image.open("ms.jpg")
    img = img.resize((400, 300), Image.LANCZOS)
    photo = ImageTk.PhotoImage(img)
    label = tk.Label(splash, image=photo)
    label.image = photo
    label.pack()

    def cerrar_splash():
        splash.destroy()

    splash.after(5000, cerrar_splash)  # 5000 ms = 5 segundos
    splash.mainloop()

# Mostrar splash antes de la app principal
if __name__ == "__main__":
    mostrar_splash()
    init_db()
    root = tk.Tk()
    app = StockApp(root)
    root.mainloop()
