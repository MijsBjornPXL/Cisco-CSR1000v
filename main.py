import customtkinter as ctk
from gui import ModernConfigPushGUI

def main():
    root = ctk.CTk()
    ModernConfigPushGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()