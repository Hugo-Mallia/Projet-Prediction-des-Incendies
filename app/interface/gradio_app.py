from fastapi import FastAPI
import gradio as gr
from app.chatbot.flameo import FlameoChatbotEnhanced
from app.chatbot.questions import SMART_AUDIT_QUESTIONS

def create_gradio_interface():
    global flameo_bot
    flameo_bot = FlameoChatbotEnhanced()

    def chat_interface(message, history):
        if history is None:
            history = []
        history = history + [{"role": "user", "content": message}]
        bot_response = flameo_bot.chat_fn(message, history)
        history = history + [{"role": "assistant", "content": bot_response}]
        return history, history  # chatbot, chat_history

    def reset_chat():
        global flameo_bot
        flameo_bot.reset_audit()
        return [], "Chat réinitialisé ! 🔄"

    def export_data():
        global flameo_bot
        data = flameo_bot.export_audit_data()
        filename = f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return f"Données exportées vers {filename} ✅"

    def get_progress():
        global flameo_bot
        if flameo_bot.audit_state.complete:
            return "Audit terminé ✅ 100%"

        total_questions = len(SMART_AUDIT_QUESTIONS)
        answered = flameo_bot.audit_state.current_idx
        progress = (answered / total_questions) * 100

        return f"Progression: {answered}/{total_questions} questions ({progress:.1f}%)"

    with gr.Blocks(
        title="Flaméo - Expert IA Sécurité Incendie",
        theme=gr.themes.Soft(),
        css="""
        .container { max-width: 1200px; margin: auto; }
        .header { background: linear-gradient(45deg, #ff6b6b, #ffa500); 
                 color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .chat-container { height: 600px; }
        .progress-bar { background: #ff6b6b; }
        """
    ) as interface:

        gr.HTML("""
        <div class="header">
            <h1>🔥 Flaméo - Expert IA en Sécurité Incendie</h1>
            <p>Audit intelligent et personnalisé de votre bâtiment</p>
        </div>
        """)

        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    label="💬 Conversation avec Flaméo",
                    height=500,
                    container=True,
                    elem_classes=["chat-container"],
                    type="messages",
                    value=[]  # Important !
                )

            with gr.Column(scale=1):
                msg = gr.Textbox(placeholder="Posez votre question ici...")
                submit_btn = gr.Button("Envoyer")
                clear_btn = gr.Button("Réinitialiser le chat")
                export_btn = gr.Button("Exporter les données")
                progress_display = gr.Markdown(get_progress())
                export_status = gr.Markdown(visible=False)
                chat_history = gr.State([])  # <-- Ajoute ceci

        submit_btn.click(
            chat_interface,
            inputs=[msg, chat_history],
            outputs=[chatbot, chat_history]
        )

        msg.submit(
            chat_interface,
            inputs=[msg, chat_history],
            outputs=[chatbot, chat_history]
        ).then(
            lambda: gr.update(value=""),
            outputs=[msg]
        ).then(
            get_progress,
            outputs=[progress_display]
        )

        clear_btn.click(
            reset_chat,
            outputs=[chatbot, progress_display]
        )

        export_btn.click(
            export_data,
            outputs=[export_status]
        ).then(
            lambda: gr.update(visible=True),
            outputs=[export_status]
        )

        interface.load(
            get_progress,
            outputs=[progress_display]
        )

    return interface.app