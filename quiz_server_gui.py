import socket
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
import json
import time

HOST = '0.0.0.0'  # listen on all interfaces
questions = []
clients = []  # list of (client_socket, nickname)
scores = {}
quiz_started = False
question_time_limit = 10
lock = threading.Lock()

def load_questions():
    with open("questions.json", "r") as f:
        return json.load(f)

def broadcast(message):
    to_remove = []
    with lock:
        current_clients = list(clients)
    for client, _ in current_clients:
        try:
            client.sendall(message.encode())
        except:
            to_remove.append(client)
    if to_remove:
        with lock:
            for c in to_remove:
                for entry in clients:
                    if entry[0] == c:
                        clients.remove(entry)
                        break

def handle_client(client_socket, addr, update_ui):
    try:
        client_socket.send("Enter your nickname: ".encode())
        nickname = client_socket.recv(1024).decode().strip()
        with lock:
            clients.append((client_socket, nickname))
            scores[nickname] = 0
        client_socket.send("Waiting for the quiz to start...\n".encode())
        update_ui()
    except:
        client_socket.close()

def accept_clients(server_socket, update_ui):
    while True:
        try:
            client_socket, addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(client_socket, addr, update_ui), daemon=True).start()
        except:
            break

def start_quiz(update_ui):
    global quiz_started, scores
    quiz_started = True
    update_ui()

    with lock:
        # Reset all scores before quiz
        scores = {nickname: 0 for _, nickname in clients}

    for i, q in enumerate(questions):
        broadcast(f"\nQuestion {i+1}: {q['question']}\n"
                  f"A: {q['A']}\nB: {q['B']}\nC: {q['C']}\nD: {q['D']}\n"
                  f"You have {question_time_limit} seconds to answer.")

        answers = {}
        answer_lock = threading.Lock()

        def collect_answer(client_socket, nickname):
            try:
                client_socket.settimeout(question_time_limit)
                answer = client_socket.recv(1024).decode().strip().upper()
                with answer_lock:
                    if nickname not in answers:  # Only accept first answer
                        answers[nickname] = answer
            except:
                with answer_lock:
                    if nickname not in answers:
                        answers[nickname] = None

        with lock:
            current_clients = list(clients)

        threads = []
        for client, nickname in current_clients:
            t = threading.Thread(target=collect_answer, args=(client, nickname))
            t.start()
            threads.append(t)

        # Wait for the full timer duration
        time.sleep(question_time_limit)

        # Process answers after timer expires
        correct = q['answer']
        feedback = []
        with lock:
            for nickname, answer in answers.items():
                if answer == correct:
                    scores[nickname] = scores.get(nickname, 0) + 1
                    feedback.append(f"{nickname} got it right!")
                else:
                    feedback.append(f"{nickname} got it wrong. Correct was {correct}.")

        # Show feedback and wait
        broadcast("\n" + "\n".join(feedback))
        time.sleep(2)  # Give players time to read feedback
        update_ui()

    final_scores = "\nFinal Scores:\n" + "\n".join([f"{n}: {s}" for n, s in scores.items()])
    broadcast(final_scores)

    max_score = max(scores.values()) if scores else 0
    winners = [n for n, s in scores.items() if s == max_score and max_score > 0]
    if winners:
        winner_text = ", ".join(winners)
        broadcast(f"\n\U0001F3C6 Winner(s): {winner_text} \U0001F3C6")
    else:
        broadcast("\nNo winner this round.")

    quiz_started = False
    update_ui()

class QuizServerGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Quiz Server")

        self.port_var = tk.StringVar(value="12345")
        self.timer_var = tk.StringVar(value="10")

        tk.Label(master, text="Port:").grid(row=0, column=0)
        self.port_entry = tk.Entry(master, textvariable=self.port_var, width=6)
        self.port_entry.grid(row=0, column=1)

        tk.Label(master, text="Timer (s):").grid(row=0, column=2)
        self.timer_entry = tk.Entry(master, textvariable=self.timer_var, width=5)
        self.timer_entry.grid(row=0, column=3)

        self.start_button = tk.Button(master, text="Start Server", command=self.start_server)
        self.start_button.grid(row=0, column=4, padx=5)

        self.start_quiz_button = tk.Button(master, text="Start Quiz", state="disabled", command=self.start_quiz)
        self.start_quiz_button.grid(row=0, column=5)

        self.client_list = scrolledtext.ScrolledText(master, height=10, width=80)
        self.client_list.grid(row=1, column=0, columnspan=6, pady=10)
        self.client_list.config(state='disabled')

        self.server_socket = None

    def update_ui(self):
        self.client_list.config(state='normal')
        self.client_list.delete(1.0, tk.END)
        self.client_list.insert(tk.END, "Connected Clients:\n")
        with lock:
            for _, nickname in clients:
                self.client_list.insert(tk.END, f"- {nickname} ({scores.get(nickname, 0)} points)\n")
        if quiz_started:
            self.client_list.insert(tk.END, "\nQuiz is running...\n")
        else:
            self.client_list.insert(tk.END, "\nQuiz not started yet.\n")
        self.client_list.config(state='disabled')

    def start_server(self):
        try:
            port = int(self.port_var.get())
            if port < 1024 or port > 65535:
                raise ValueError
        except:
            messagebox.showerror("Invalid Port", "Please enter a valid port number (1024-65535).")
            return

        global questions
        questions = load_questions()

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((HOST, port))
        self.server_socket.listen()

        threading.Thread(target=accept_clients, args=(self.server_socket, self.update_ui), daemon=True).start()

        self.start_button.config(state='disabled')
        self.start_quiz_button.config(state='normal')
        self.update_ui()

    def start_quiz(self):
        global question_time_limit
        try:
            question_time_limit = int(self.timer_var.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number for the timer.")
            return

        with lock:
            if len(clients) < 3:
                messagebox.showwarning("Not enough players", "Minimum 3 players required to start the quiz.")
                return

        threading.Thread(target=start_quiz, args=(self.update_ui,), daemon=True).start()


def main():
    root = tk.Tk()
    app = QuizServerGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
