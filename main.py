import os
import platform
import subprocess
from datetime import datetime
import sqlite3
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivymd.app import MDApp
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.list import OneLineListItem
from kivymd.uix.screen import MDScreen
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivymd.uix.list import MDList
from kivymd.uix.label import MDLabel
from kivymd.uix.gridlayout import MDGridLayout

# Conditional import for Android modules
if platform.system() == "Android":
    from jnius import autoclass
    from android.storage import primary_external_storage_path
    from android.content import Intent

KV = '''
MDScreen:
    id: screen_manager
    MDBottomNavigation:
        id: bottom_nav
        MDBottomNavigationItem:
            name: 'screen 1'
            text: 'My Store'
            icon: 'store-alert-outline'
            MDGridLayout:
                cols: 2
                MDBoxLayout:
                    orientation: 'vertical'
                    spacing: dp(10)
                    padding: dp(20)
                    MDBoxLayout:
                        adaptive_height: True
                        MDIconButton:
                            icon: 'magnify'
                        MDTextField:
                            id: search_field
                            hint_text: 'Search product'
                            on_text: app.search_product(self.text)
                    ScrollView:
                        MDList:
                            id: show_list
                MDBoxLayout:
                    orientation: 'vertical'
                    spacing: dp(10)
                    padding: dp(20)
                    MDBoxLayout:
                        adaptive_height: True
                        MDIconButton:
                            icon: 'home-outline'
                        MDLabel:
                            id: check_out
                            text: 'Checkout'
                            halign: 'center'
                        MDIconButton:
                            icon: 'cart-outline'
                    MDSeparator:
                        size_hint_x: 1
                        pos_hint: {'center_x': .5, 'center_y': .5}
                    ScrollView:
                        MDList:
                            id: checkout_list
                    MDLabel:
                        id: total_label
                        text: 'Total: #0.00'
                        halign: 'center'
                    MDRaisedButton:
                        text: 'Checkout and Print Receipt'
                        on_release: app.show_save_as_popup()

        MDBottomNavigationItem:
            name: 'screen 2'
            text: 'Print Invoice'
            icon: 'printer'
            MDLabel:
                id: print_invoice_label
                halign: 'center'
            MDBoxLayout:
                id: show_invoice
                orientation: 'vertical'
                padding: dp(20)
                ScrollView:
                    MDLabel:
                        id: receipt_content
                        halign: 'center'
            MDRaisedButton:
                text: 'Print Now'
                on_release: app.print_now()

        MDBottomNavigationItem:
            id: screen_3
            name: 'screen 3'
            text: 'Out of stock'
            icon: 'access-point'
            badge_icon: "numeric-10"
            BoxLayout:
                orientation: 'vertical'
                spacing: dp(10)
                padding: dp(20)
                MDLabel:
                    text: 'List of out of stock or low stock items'
                    size_hint: 0.9, 0.1
                    halign: 'center'
                ScrollView:
                    MDList:
                        id: stock_list

        MDBottomNavigationItem:
            id: screen_4
            name: 'screen 4'
            text: 'Admin'
            icon: 'account'
            BoxLayout:
                id: admin_box
                orientation: 'vertical'
                spacing: dp(10)
                padding: dp(20)
                MDTextField:
                    id: admin_username
                    hint_text: "Username"
                    pos_hint: {"center_x": 0.5, "center_y": 0.5}
                MDTextField:
                    id: admin_password
                    hint_text: "Password"
                    password: True
                    pos_hint: {"center_x": 0.5, "center_y": 0.5}
                MDRaisedButton:
                    text: "Login"
                    pos_hint: {"center_x": 0.5, "center_y": 0.5}
                    on_release: app.admin_login()
'''

class MyPos(MDApp):
    def build(self):
        self.theme_cls.theme_style = 'Dark'
        self.theme_cls.primary_palette = 'Gray'
        self.cart = []  # List to hold cart items
        self.total = 0.00  # To keep track of the total amount
        self.receipt_folder = "receipts"  # Folder to save receipts
        self.receipt_file = "receipt.txt"  # Default receipt filename as text file
        self.is_admin = False  # To track admin login status
        self.connection = sqlite3.connect('pos.db')
        self.cursor = self.connection.cursor()
        return Builder.load_string(KV)

    def on_start(self):
        self.load_products()  # Load all products initially
        self.load_stock_items()  # Load stock items on startup

    def load_products(self):
        show_list = self.root.ids.show_list
        show_list.clear_widgets()  # Clear existing items
        query = self.cursor.execute("SELECT * FROM product")
        for row in query:
            onelist = OneLineListItem(text=row[2])
            onelist.bind(on_press=lambda x, r=row: self.show_product_popup(r))
            show_list.add_widget(onelist)

    def search_product(self, search_text):
        show_list = self.root.ids.show_list
        show_list.clear_widgets()  # Clear existing items

        if search_text:  # If there's text to search for
            query = self.cursor.execute("SELECT * FROM product WHERE product LIKE ?", ('%' + search_text + '%',))
            for row in query:
                onelist = OneLineListItem(text=row[2])
                onelist.bind(on_press=lambda x, r=row: self.show_product_popup(r))
                show_list.add_widget(onelist)
        else:
            self.load_products()

    def show_product_popup(self, product):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Label(text=f"Product: {product[2]}"))
        content.add_widget(Label(text=f"Price: #{product[8]}"))
        content.add_widget(Label(text=f"Stock: {product[7]}"))
        self.quantity_input = MDTextField(text='', hint_text="Enter quantity")
        content.add_widget(self.quantity_input)
        add_button = MDRaisedButton(text="Add to Cart", on_release=lambda x: self.add_to_cart(product))
        content.add_widget(add_button)
        self.popup = Popup(title="Product Details", content=content, size_hint=(0.8, 0.8))
        self.popup.open()

    def add_to_cart(self, product):
        try:
            quantity = int(self.quantity_input.text)
        except ValueError:
            self.show_error("Please enter a valid quantity!")
            return
        try:
            stock_quantity = int(product[7])  # Convert stock to integer
        except ValueError:
            self.show_error("Invalid stock quantity!")
            return
        if quantity <= 0 or quantity > stock_quantity:
            self.show_error("Invalid quantity!")
            return
        try:
            price = float(product[8])  # Convert price to float
        except ValueError:
            self.show_error("Invalid price!")
            return
        # Update stock in the database
        new_stock_quantity = stock_quantity - quantity
        self.cursor.execute("UPDATE product SET stock = ? WHERE id = ?", (new_stock_quantity, product[0]))
        self.connection.commit()
        # Add product to cart
        self.cart.append((product, quantity))
        self.total += price * quantity  # Use the converted price
        # Update checkout list and total label
        self.update_checkout_list()
        self.root.ids.total_label.text = f'Total: #{self.total:.2f}'
        self.popup.dismiss()
        self.load_products()

    def update_checkout_list(self):
        checkout_list = self.root.ids.checkout_list
        checkout_list.clear_widgets()
        for item in self.cart:
            product, quantity = item
            list_item = OneLineListItem(text=f"{product[2]} x{quantity} - #{float(product[8]) * quantity:.2f}")
            list_item.bind(on_press=lambda x, r=item: self.confirm_remove_item(r))
            checkout_list.add_widget(list_item)

    def confirm_remove_item(self, item):
        product, quantity = item
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Label(text=f"Are you sure you want to remove {product[2]} x{quantity}?"))
        confirm_button = MDRaisedButton(text="Confirm", on_release=lambda x: self.remove_item(item))
        cancel_button = MDRaisedButton(text="Cancel", on_release=lambda x: self.popup.dismiss())
        content.add_widget(confirm_button)
        content.add_widget(cancel_button)
        self.popup = Popup(title="Remove Item", content=content, size_hint=(0.8, 0.4))
        self.popup.open()

    def remove_item(self, item):
        product, quantity = item
        # Update stock in the database
        self.cursor.execute("UPDATE product SET stock = stock + ? WHERE id = ?", (quantity, product[0]))
        self.connection.commit()
        # Remove product from cart
        self.cart.remove(item)
        self.total -= float(product[8]) * quantity
        # Update checkout list and total label
        self.update_checkout_list()
        self.root.ids.total_label.text = f'Total: #{self.total:.2f}'
        self.popup.dismiss()
        self.load_products()  # Load all products initially


    def cancel_checkout(self):
        self.cart.clear()  # Clear the cart
        self.total = 0.00  # Reset total
        self.root.ids.total_label.text = 'Total: #0.00'  # Update total label
        self.root.ids.checkout_list.clear_widgets()  # Clear checkout list

    def show_save_as_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        self.save_as_input = MDTextField(hint_text="Enter file name")
        save_button = MDRaisedButton(text="Save", on_release=self.save_as_receipt)
        cancel_button = MDRaisedButton(text="Cancel", on_release=lambda x: self.popup.dismiss())
        content.add_widget(self.save_as_input)
        content.add_widget(save_button)
        content.add_widget(cancel_button)
        self.popup = Popup(title="Save Receipt As", content=content, size_hint=(0.8, 0.4))
        self.popup.open()

    def save_as_receipt(self, *args):
        file_name = self.save_as_input.text.strip()
        if not file_name:
            self.show_error("Please enter a valid file name!")
            return

        self.receipt_file = file_name + ".txt"  # Set new receipt file name with .txt extension
        self.popup.dismiss()  # Close the popup
        self.checkout_and_print()

    def checkout_and_print(self):
        if not self.cart:
            self.show_error("Cart is empty!")
            return

        # Store total in the sales database
        conn = sqlite3.connect('pos.db')
        conn.execute("INSERT INTO sales (total) VALUES (?)", (self.total,))
        conn.commit()
        conn.close()

        receipt_content = self.save_receipt_to_text()  # Save the receipt and get content as string
        self.show_receipt_in_invoice_screen(receipt_content)  # Show the receipt in the 'show_invoice' widget
        self.cancel_checkout()  # Clear cart after checkout

    def save_receipt_to_text(self):
        if not os.path.exists(self.receipt_folder):
            os.makedirs(self.receipt_folder)
        receipt_path = os.path.join(self.receipt_folder, self.receipt_file)
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        receipt_content = "==== Afotect Comm. ====\n"
        receipt_content += " Sales Receipt\n"
        receipt_content += "-------------------------------------\n"
        for item in self.cart:
            product, quantity = item
            receipt_content += f"{product[2]} unit: {quantity} - #{float(product[8]) * quantity:.2f}\n"
        receipt_content += "======================\n"
        receipt_content += f"Total: #{self.total:.2f}\n"
        receipt_content += "======================\n"
        receipt_content += "Thank you for your purchase!\n"
        receipt_content += f"Date: {current_datetime}\n"

        with open(receipt_path, 'w') as f:
            f.write(receipt_content)

        return receipt_content

    def show_receipt_in_invoice_screen(self, receipt_content):
        self.root.ids.receipt_content.text = receipt_content

    def print_now(self):
        # Get the receipt content
        receipt_content = self.root.ids.receipt_content.text
        # Check if receipt_content is empty
        if not receipt_content.strip():
            self.show_error("Receipt content is empty. Please \n generate a receipt before printing.")
            return
        # This method will handle the actual printing to a hardware printer
        if platform.system() == "Android":
            self.print_to_android_printer()
        else:
            self.desktop_print()

    def print_to_android_printer(self):
        # Implement Android printing here
        from jnius import autoclass

        # Get the necessary classes
        PrintManager = autoclass('android.print.PrintManager')
        PrintDocumentAdapter = autoclass('android.print.PrintDocumentAdapter')
        Intent = autoclass('android.content.Intent')
        Context = autoclass('android.content.Context')
        Activity = autoclass('android.app.Activity')

        # Get the current activity
        activity = Activity.mActivity

        # Create a print manager instance
        print_manager = activity.getSystemService(Context.PRINT_SERVICE)

        # Create a print adapter
        class MyPrintDocumentAdapter(PrintDocumentAdapter):
            def onLayout(self, oldAttributes, newAttributes, result, metadata):
                # Define the layout for the printed document
                result.onLayoutFinished(newAttributes, True)

            def onWrite(self, pages, destination, cancellationSignal, result):
                # Write the content to print
                receipt_path = os.path.join(self.receipt_folder, self.receipt_file)
                with open(receipt_path, 'r') as f:
                    content = f.read()
                # Create a document
                pdf_document = autoclass('android.graphics.pdf.PdfDocument')
                document = pdf_document()
                # Create a page
                page_info = pdf_document.PageInfo.Builder(595, 842, 1).create()  # A4 size
                page = document.startPage(page_info)
                canvas = page.getCanvas()
                # Draw the content on the canvas
                canvas.drawText(content, 10, 25)  # Adjust the position as needed
                document.finishPage(page)
                # Write the document to the output
                document.writeTo(destination)
                document.close()
                result.onWriteFinished([destination])

        # Create the print document adapter
        adapter = MyPrintDocumentAdapter()
        print_manager.print_("Receipt", adapter, None)

    def desktop_print(self):
        # For desktop printing, using the system's print command
        receipt_path = os.path.join(self.receipt_folder, self.receipt_file)
        if platform.system() == "Windows":
            os.startfile(receipt_path, "print")
        else:
            pass
            # subprocess.run(["lp", receipt_path])  # For Linux and macOS

    def show_error(self, message):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Label(text=message))
        close_button = MDRaisedButton(text="Close", on_release=lambda x: self.popup.dismiss())
        content.add_widget(close_button)
        self.popup = Popup(title="Error", content=content, size_hint=(0.8, 0.4))
        self.popup.open()




    def load_stock_items(self):
        stock_list = self.root.ids.stock_list
        stock_list.clear_widgets()  # Clear existing items

        conn = sqlite3.connect('pos.db')
        count_query = conn.execute("SELECT COUNT(*) FROM product WHERE stock <= 5")
        count = count_query.fetchone()[0]

        query = conn.execute("SELECT * FROM product WHERE stock <= 5")
        for row in query:
            onelist = OneLineListItem(text=f"{row[2]} - {row[7]} left")
            stock_list.add_widget(onelist)

        conn.close()  # Close the database connection

        # Access the `MDBottomNavigationItem` by its ID
        out_of_stock_tab = self.root.ids['screen_3']

        # Update the `badge_icon`
        out_of_stock_tab.badge_icon = f"numeric-{count}" if count > 0 else ""
            



    def admin_login(self):
        username = self.root.ids.admin_username.text
        password = self.root.ids.admin_password.text
        if username == "admin" and password == "admin":
            self.is_admin = True
            self.show_admin_dashboard()
        else:
            self.show_error("Invalid username or password!")

    def show_admin_dashboard(self):
        if self.is_admin:
            self.root.ids.admin_box.clear_widgets()
            admin_screen = MDScreen()

            grid_layout = MDGridLayout(cols=1, spacing=10, padding=20)

            view_products_button = MDRaisedButton(text="View Products", on_release=lambda x: self.view_products())
            add_product_button = MDRaisedButton(text="Add Product", on_release=lambda x: self.show_add_product_form())
            update_stock_button = MDRaisedButton(text="Update Stock", on_release=lambda x: self.show_update_stock_form())
            delete_product_button = MDRaisedButton(text="Delete Product", on_release=lambda x: self.show_delete_product_form())
            logout = MDRaisedButton(text="Logout", on_release=lambda x: self.logout())

            grid_layout.add_widget(view_products_button)
            grid_layout.add_widget(add_product_button)
            grid_layout.add_widget(update_stock_button)
            grid_layout.add_widget(delete_product_button)
            grid_layout.add_widget(logout)

            admin_screen.add_widget(grid_layout)
            self.root.ids.admin_box.add_widget(admin_screen)
            
            
            
            
            

    def view_products(self):
        self.root.ids.admin_box.clear_widgets()
        scroll_view = ScrollView()
        product_list = MDList()
        scroll_view.add_widget(product_list)

        query = self.cursor.execute("SELECT * FROM product")
        for row in query:
            product_item = OneLineListItem(text=f"{row[2]} - Price: #{row[8]} - Stock: {row[7]}")
            product_item.bind(on_press=lambda x, r=row: self.show_restock_popup(r))
            product_list.add_widget(product_item)

        self.root.ids.admin_box.add_widget(scroll_view)
        back_btn = MDRaisedButton(text="Back", on_release=lambda x: self.back_btn())
        self.root.ids.admin_box.add_widget(back_btn)



    def back_btn(self):
    	self.show_admin_dashboard()
    	
    	
    def logout(self):
          self.root.ids.admin_box.clear_widgets()
          admin_screen = MDScreen()
          label = MDLabel(text='You have successfully Logout. Please restart this app', halign='center', font_size=40)
          admin_screen.add_widget(label)
          self.root.ids.admin_box.add_widget(admin_screen)
              	
    		
    def show_restock_popup(self, product):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        product_name_input = MDTextField(text=product[2], hint_text="Enter product name")
        product_stock_input = MDTextField(text=str(product[7]), hint_text="Enter stock quantity")
        product_price_input = MDTextField(text=str(product[8]), hint_text="Enter Product Price")
        content.add_widget(product_name_input)
        content.add_widget(product_stock_input)
        content.add_widget(product_price_input)
        update_button = MDRaisedButton(text="Update", on_release=lambda x: self.save_product_update(product[0],
                                                                                                    product_name_input.text,
                                                                                                    product_stock_input.text,
                                                                                                    product_price_input.text))
        delete_button = MDRaisedButton(text="Delete", on_release=lambda x: self.delete_products(product))
        content.add_widget(update_button)
        content.add_widget(delete_button)
        self.popup = Popup(title="Update Product", content=content, size_hint=(0.8, 0.8))
        self.popup.open()


    def save_product_update(self, product_id, product_name, product_stock, product_price):
        try:
            self.cursor.execute("UPDATE product SET product = ?, stock = ?, price = ? WHERE id = ?", (product_name, product_stock, product_price, product_id))
            self.connection.commit()
            self.popup.dismiss()
            
            self.view_products()
        except sqlite3.Error as e:
            self.show_popup("Database Error", str(e))

    def delete_products(self, product):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(MDLabel(text=f"Are you sure you want to delete '{product[2]}'?", halign='center'))
        delete_button = MDRaisedButton(text="Delete", on_release=lambda x: self.confirm_delete(product[0]))
        cancel_button = MDRaisedButton(text="Cancel", on_release=lambda x: self.popup.dismiss())
        content.add_widget(delete_button)
        content.add_widget(cancel_button)
        self.popup = Popup(title="Delete Product", content=content, size_hint=(0.8, 0.8))
        self.popup.open()

    def confirm_delete(self, product_id):
        try:
            self.cursor.execute("DELETE FROM product WHERE id = ?", (product_id,))
            self.connection.commit()
            self.popup.dismiss()
            
            self.view_products()
        except sqlite3.Error as e:
            self.show_popup("Database Error", str(e))












    def show_add_product_form(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        self.product_name_input = MDTextField(hint_text="Product Name")
        self.product_price_input = MDTextField(hint_text="Price", input_filter='float')
        self.product_stock_input = MDTextField(hint_text="Stock", input_filter='int')
        content.add_widget(self.product_name_input)
        content.add_widget(self.product_price_input)
        content.add_widget(self.product_stock_input)
        save_button = MDRaisedButton(text="Add Product", on_release=self.add_product)
        content.add_widget(save_button)
        self.popup = Popup(title="Add Product", content=content, size_hint=(0.8, 0.8))
        self.popup.open()

    def add_product(self, *args):
        name = self.product_name_input.text
        try:
            price = float(self.product_price_input.text)
            stock = int(self.product_stock_input.text)
        except ValueError:
            self.show_error("Invalid input for price or stock!")
            return

        if name and price > 0 and stock >= 0:
            self.cursor.execute("INSERT INTO product (product, price, stock) VALUES (?, ?, ?)",
                                (name, price, stock))
            self.connection.commit()
            self.popup.dismiss()
            self.show_error("Product added successfully!")
        else:
            self.show_error("Please fill in all fields with valid data!")

    def show_update_stock_form(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        self.product_name_input = MDTextField(hint_text="Product Name")
        self.new_stock_input = MDTextField(hint_text="New Stock", input_filter='int')
        content.add_widget(self.product_name_input)
        content.add_widget(self.new_stock_input)
        update_button = MDRaisedButton(text="Update Stock", on_release=self.update_stock)
        content.add_widget(update_button)
        self.popup = Popup(title="Update Stock", content=content, size_hint=(0.8, 0.8))
        self.popup.open()

    def update_stock(self, *args):
        name = self.product_name_input.text
        try:
            new_stock = int(self.new_stock_input.text)
        except ValueError:
            self.show_error("Invalid stock value!")
            return

        if name and new_stock >= 0:
            self.cursor.execute("UPDATE product SET stock = ? WHERE product = ?", (new_stock, name))
            if self.cursor.rowcount == 0:
                self.show_error("Product not found!")
            else:
                self.connection.commit()
                self.popup.dismiss()
                self.show_error("Stock updated successfully!")
        else:
            self.show_error("Please enter a valid product name and stock quantity!")

    def show_delete_product_form(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        self.product_name_input = MDTextField(hint_text="Product Name")
        content.add_widget(self.product_name_input)
        delete_button = MDRaisedButton(text="Delete Product", on_release=self.delete_product)
        content.add_widget(delete_button)
        self.popup = Popup(title="Delete Product", content=content, size_hint=(0.8, 0.4))
        self.popup.open()

    def delete_product(self, *args):
        name = self.product_name_input.text
        if name:
            self.cursor.execute("DELETE FROM product WHERE product = ?", (name,))
            if self.cursor.rowcount == 0:
                self.show_error("Product not found!")
            else:
                self.connection.commit()
                self.popup.dismiss()
                self.show_error("Product deleted successfully!")
        else:
            self.show_error("Please enter a valid product name!")

    def show_error(self, message):
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Label(text=message))
        close_button = MDRaisedButton(text="Close", on_release=lambda x: self.popup.dismiss())
        content.add_widget(close_button)
        self.popup = Popup(title="Error", content=content, size_hint=(0.8, 0.4))
        self.popup.open()

if __name__ == '__main__':
    MyPos().run()
