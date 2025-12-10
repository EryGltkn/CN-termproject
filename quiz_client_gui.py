import socket
import threading
import tkinter as tk
import time

class QuizClientGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Quiz Client")

        self.client_socket = None
        self.timer_thread = None
        self.remaining_time = 0

        self.login_frame = tk.Frame(master)
        self.login_frame.pack(padx=10, pady=10)

        tk.Label(self.login_frame, text="Host:").grid(row=0, column=0)
        self.host_entry = tk.Entry(self.login_frame)
        self.host_entry.insert(0, "localhost")
        self.host_entry.grid(row=0, column=1)

        tk.Label(self.login_frame, text="Port:").grid(row=1, column=0)
        self.port_entry = tk.Entry(self.login_frame)
        self.port_entry.insert(0, "12345")
        self.port_entry.grid(row=1, column=1)

        tk.Label(self.login_frame, text="Username:").grid(row=2, column=0)
        self.username_entry = tk.Entry(self.login_frame)
        self.username_entry.grid(row=2, column=1)

        self.connect_button = tk.Button(self.login_frame, text="Connect", command=self.connect_to_server)
        self.connect_button.grid(row=3, column=0, columnspan=2, pady=5)

        self.quiz_frame = tk.Frame(master)

        self.top_bar = tk.Frame(self.quiz_frame)
        self.top_bar.pack(fill='x')

        self.timer_label = tk.Label(self.top_bar, text="", anchor='w')
        self.timer_label.pack(side='left', padx=5)

        self.question_label = tk.Label(self.quiz_frame, text="Waiting for quiz to start...", wraplength=400, justify="left")
        self.question_label.pack(pady=10)

        self.answer_buttons = []
        for opt in ['A', 'B', 'C', 'D']:
            btn = tk.Button(self.quiz_frame, text=opt, width=20, state="disabled", command=lambda o=opt: self.send_answer(o))
            btn.pack(pady=2)
            self.answer_buttons.append(btn)

        # Handle window close event to notify server
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def connect_to_server(self):
        host = self.host_entry.get()
        port = int(self.port_entry.get())
        username = self.username_entry.get()

        if not username:
            self.question_label.config(text="Username required.")
            return

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect((host, port))
        except:
            self.question_label.config(text="Connection failed.")
            return

        self.client_socket.send(username.encode())

        self.login_frame.pack_forget()
        self.quiz_frame.pack(padx=10, pady=10, fill='both')

        threading.Thread(target=self.receive_messages, daemon=True).start()

    def receive_messages(self):
        while True:
            try:
                message = self.client_socket.recv(1024).decode()
                if not message:
                    break
                self.display_question_or_info(message)
            except:
                break
        # Connection lost or closed
        self.client_socket.close()
        self.master.quit()  # Close client GUI when server disconnects

    def display_question_or_info(self, message):
        lines = message.strip().split('\n')
        if any(line.startswith("Question") for line in lines):
            question_text = '\n'.join(lines[:-1])
            self.question_label.config(text=question_text)
            self.enable_buttons(True)

            for line in lines:
                if "You have" in line and "seconds" in line:
                    try:
                        self.remaining_time = int(line.split("You have ")[1].split(" seconds")[0])
                    except:
                        self.remaining_time = 10
                    break

            if self.timer_thread and self.timer_thread.is_alive():
                self.timer_thread.join()
            self.timer_thread = threading.Thread(target=self.update_timer, daemon=True)
            self.timer_thread.start()

        elif message.startswith("Final Scores:"):
            self.question_label.config(text=message)
            self.enable_buttons(False)
            self.timer_label.config(text="")

        else:
            # This is feedback or other message
            self.question_label.config(text=message)
            self.enable_buttons(False)
            self.timer_label.config(text="")

    def update_timer(self):
        while self.remaining_time > 0:
            self.timer_label.config(text=f"Time left: {self.remaining_time}s")
            time.sleep(1)
            self.remaining_time -= 1
        self.timer_label.config(text="Time's up!")
        self.enable_buttons(False)

    def enable_buttons(self, enable):
        state = "normal" if enable else "disabled"
        for btn in self.answer_buttons:
            btn.config(state=state)

    def send_answer(self, option):
        try:
            self.client_socket.send(option.encode())
            self.enable_buttons(False)  # Disable buttons immediately after sending answer
        except:
            pass

    def on_closing(self):
        try:
            if self.client_socket:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
        except:
            pass
        self.master.destroy()

def main():
    root = tk.Tk()
    app = QuizClientGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
